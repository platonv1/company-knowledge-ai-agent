"""Run the evaluation suite.

Two modes:

    python -m scripts.run_eval                 # retrieval metrics only, no API key needed
    python -m scripts.run_eval --with-answers  # also generate and judge answers
    python -m scripts.run_eval --sweep         # calibrate the relevance floor

The sweep retrieves candidates once per question and then re-applies the gate in
memory for every threshold combination, so calibrating is cheap. Without that,
tuning the floor means re-embedding the golden set for each value and nobody
does it twice.

Follow-up cases are evaluated with the raw follow-up text in retrieval-only
mode. They are expected to fail there -- that is the measurement that justifies
the query-rewriting step, rather than an assertion that it is needed.
"""

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import yaml

from app.core.config import get_settings
from app.core.database import dispose_engine, get_session_factory
from app.core.logging import configure_logging
from app.rag.embeddings import build_embedding_service
from app.rag.retriever import RetrievalConfig, apply_relevance_gate
from app.repositories.vector_store import PgVectorStore, SearchFilters
from app.services.document_service import get_or_create_organization
from scripts.eval_core import EvalSummary, Outcome, RetrievedChunk, summarise

DEFAULT_GOLDEN_SET = Path("eval/corpus_facts.yaml")
RESULTS_DIR = Path("eval/results")

# Candidate pool size for the sweep: wide enough that a higher top_k has
# something to select from.
SWEEP_SEARCH_K = 20


def load_golden_set(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"{path} not found. Run `python -m scripts.generate_corpus` first.")
    return yaml.safe_load(path.read_text())


def build_cases(golden: dict) -> list[dict]:
    cases = [
        {
            "case_id": fact["id"],
            "kind": "fact",
            "question": fact["question"],
            "category": fact.get("category", "direct"),
            "expected_document": fact["document"],
            "expected_page": fact["page"],
            "expected_answer": fact["answer"],
        }
        for fact in golden["facts"]
    ]
    cases += [
        {
            "case_id": item["id"],
            "kind": "unanswerable",
            "question": item["question"],
            "category": "unanswerable",
            "expected_document": None,
            "expected_page": None,
            "expected_answer": None,
        }
        for item in golden["unanswerable"]
    ]
    cases += [
        {
            "case_id": item["id"],
            "kind": "followup",
            # Retrieval-only mode sees the bare follow-up, with no rewriting.
            "question": item["turns"][-1],
            "category": "followup",
            "expected_document": item["document"],
            "expected_page": None,
            "expected_answer": " / ".join(item["answer_contains"]),
            "turns": item["turns"],
        }
        for item in golden["followups"]
    ]
    return cases


async def retrieve_candidates(store, embedder, org_id, cases: list[dict]) -> dict[str, list]:
    """Retrieve a wide candidate pool once per case."""
    candidates: dict[str, list] = {}
    for case in cases:
        embedding = await embedder.embed_query(case["question"])
        candidates[case["case_id"]] = await store.search(
            embedding, SearchFilters(org_id=org_id), limit=SWEEP_SEARCH_K
        )
    return candidates


def to_outcomes(
    cases: list[dict], candidates: dict[str, list], config: RetrievalConfig
) -> list[Outcome]:
    outcomes = []
    for case in cases:
        kept, _ = apply_relevance_gate(candidates[case["case_id"]], config)
        outcomes.append(
            Outcome(
                case_id=case["case_id"],
                kind=case["kind"],
                question=case["question"],
                category=case["category"],
                expected_document=case["expected_document"],
                expected_page=case["expected_page"],
                retrieved=[
                    RetrievedChunk(
                        document=r.document_filename,
                        page_start=r.page_start,
                        page_end=r.page_end,
                        score=r.score,
                    )
                    for r in kept
                ],
            )
        )
    return outcomes


def print_summary(summary: EvalSummary, label: str) -> None:
    print(f"\n{label}")
    print("-" * len(label))
    print(f"  Answerable cases            {summary.answerable}")
    print(
        f"  Page hit@k                  {summary.page_hit_rate:6.1%}  "
        f"({summary.page_hits}/{summary.answerable})"
    )
    print(
        f"  Document hit@k              {summary.document_hit_rate:6.1%}  "
        f"({summary.document_hits}/{summary.answerable})"
    )
    print(
        f"  Top-1 document correct      {summary.top1_rate:6.1%}  "
        f"({summary.top1_correct}/{summary.answerable})"
    )
    print(
        f"  Over-refusal (bad)          {summary.over_refusal_rate:6.1%}  "
        f"({summary.over_refusals}/{summary.answerable})"
    )
    print(f"  Unanswerable cases          {summary.unanswerable}")
    print(
        f"  Refusal accuracy            {summary.refusal_accuracy:6.1%}  "
        f"({summary.correct_refusals}/{summary.unanswerable})"
    )
    print(f"  Version leaks (must be 0)   {summary.version_leaks}")
    if summary.end_to_end_refusal_accuracy is not None:
        print(
            f"  Refusal accuracy, end to end {summary.end_to_end_refusal_accuracy:5.1%}  "
            f"({summary.refused_end_to_end}/{summary.unanswerable_answered})"
        )
    if summary.answer_match_rate is not None:
        print(
            f"  Answer match                {summary.answer_match_rate:6.1%}  "
            f"({summary.answers_matched}/{summary.answered})"
        )
        print(f"  Citations all resolvable    {summary.citations_valid}/{summary.answered}")
    if summary.faithfulness_rate is not None:
        print(
            f"  Faithfulness (judged)       {summary.faithfulness_rate:6.1%}  "
            f"({summary.faithful}/{summary.answered})"
        )


def print_by_category(outcomes: list[Outcome]) -> None:
    from scripts.eval_core import page_hit

    categories: dict[str, list[Outcome]] = {}
    for outcome in outcomes:
        categories.setdefault(outcome.category, []).append(outcome)

    print("\nBy category")
    print("-----------")
    for category in sorted(categories):
        group = categories[category]
        if category == "unanswerable":
            correct = sum(1 for o in group if o.retrieved_nothing)
            print(f"  {category:<16} {correct}/{len(group)} correctly refused")
        else:
            hits = sum(1 for o in group if page_hit(o))
            print(f"  {category:<16} {hits}/{len(group)} page hits")


def print_failures(outcomes: list[Outcome], limit: int = 12) -> None:
    from scripts.eval_core import page_hit

    failures = [
        o
        for o in outcomes
        if (o.kind == "unanswerable" and not o.retrieved_nothing)
        or (o.kind != "unanswerable" and not page_hit(o))
    ]
    if not failures:
        print("\nNo failures.")
        return

    print(f"\nFailures ({len(failures)}), first {min(limit, len(failures))}")
    print("-" * 40)
    for outcome in failures[:limit]:
        got = (
            f"{outcome.retrieved[0].document} p{outcome.retrieved[0].page_start} "
            f"({outcome.retrieved[0].score:.3f})"
            if outcome.retrieved
            else "nothing retrieved"
        )
        expected = (
            f"{outcome.expected_document} p{outcome.expected_page}"
            if outcome.expected_document
            else "refusal"
        )
        print(f"  {outcome.case_id:<28} expected {expected:<42} got {got}")


def print_sweep(rows: list[tuple[RetrievalConfig, EvalSummary]]) -> None:
    print("\nThreshold sweep")
    print("---------------")
    print(
        f"  {'floor':>6} {'dropoff':>8} {'top_k':>6} {'page hit':>9} "
        f"{'top-1':>7} {'refusal':>8} {'over-ref':>9} {'leaks':>6}"
    )
    for config, summary in rows:
        print(
            f"  {config.relevance_floor:>6.2f} {config.relative_dropoff:>8.2f} "
            f"{config.top_k:>6} {summary.page_hit_rate:>8.1%} {summary.top1_rate:>7.1%} "
            f"{summary.refusal_accuracy:>8.1%} {summary.over_refusal_rate:>9.1%} "
            f"{summary.version_leaks:>6}"
        )
    print(
        "\n  Read this for the best page hit and refusal accuracy at the lowest\n"
        "  over-refusal. Refusal accuracy alone is maximised by refusing\n"
        "  everything, so the two columns must be read together."
    )


def write_results(
    path: Path, summary: EvalSummary, outcomes: list[Outcome], settings, config
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "config": asdict(config),
        "summary": {
            "page_hit_rate": summary.page_hit_rate,
            "document_hit_rate": summary.document_hit_rate,
            "top1_rate": summary.top1_rate,
            "refusal_accuracy": summary.refusal_accuracy,
            "over_refusal_rate": summary.over_refusal_rate,
            "version_leaks": summary.version_leaks,
            "answer_match_rate": summary.answer_match_rate,
            "faithfulness_rate": summary.faithfulness_rate,
        },
        "outcomes": [asdict(o) for o in outcomes],
    }
    path.write_text(json.dumps(payload, indent=2, default=str))
    print(f"\nWrote {path}")


async def run(args) -> int:
    configure_logging()
    settings = get_settings()

    golden = load_golden_set(args.golden)
    cases = build_cases(golden)
    archived = {d["filename"] for d in golden["documents"] if d.get("doc_status") == "archived"}

    async with get_session_factory()() as session:
        organization = await get_or_create_organization(
            session, name=settings.company_name, slug=settings.org_slug
        )
        store = PgVectorStore(session)

        indexed = await store.count_chunks(organization.id)
        if indexed == 0:
            raise SystemExit(
                "The knowledge base is empty. Run "
                "`python -m scripts.ingest_documents documents/ --reset` first."
            )

        embedder = build_embedding_service(settings)

        print(
            f"Golden set: {len(cases)} cases "
            f"({sum(1 for c in cases if c['kind'] == 'fact')} facts, "
            f"{sum(1 for c in cases if c['kind'] == 'unanswerable')} unanswerable, "
            f"{sum(1 for c in cases if c['kind'] == 'followup')} follow-ups)"
        )
        model_label = (
            settings.embedding_model if settings.embedding_provider == "openai" else "offline"
        )
        print(
            f"Index: {indexed} chunks | embeddings: {settings.embedding_provider} ({model_label})"
        )

        candidates = await retrieve_candidates(store, embedder, organization.id, cases)

        if args.sweep:
            rows = []
            for floor in args.floors:
                for top_k in args.top_ks:
                    config = RetrievalConfig(
                        search_k=SWEEP_SEARCH_K,
                        top_k=top_k,
                        relevance_floor=floor,
                        relative_dropoff=args.dropoff,
                    )
                    outcomes = to_outcomes(cases, candidates, config)
                    rows.append((config, summarise(outcomes, archived)))
            print_sweep(rows)
            await dispose_engine()
            return 0

        config = RetrievalConfig.from_settings(settings)
        outcomes = to_outcomes(cases, candidates, config)

        if args.with_answers:
            outcomes = await score_answers(session, settings, cases, outcomes, organization.id)

        summary = summarise(outcomes, archived)
        print_summary(
            summary, f"Retrieval evaluation (floor={config.relevance_floor}, top_k={config.top_k})"
        )
        print_by_category(outcomes)
        print_failures(outcomes)

        if args.save:
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            write_results(RESULTS_DIR / f"eval-{stamp}.json", summary, outcomes, settings, config)

    await dispose_engine()
    return 0


async def score_answers(session, settings, cases, outcomes, org_id):
    """Generate answers and judge them. Requires a live model."""
    from dataclasses import replace

    from app.llm.openai_provider import build_llm_service
    from app.llm.prompts import REFUSAL_MARKER
    from app.rag.embeddings import build_embedding_service
    from app.rag.retriever import RetrievalConfig, Retriever
    from app.repositories.conversation_repository import ConversationRepository
    from app.services.chat_service import ChatService

    service = ChatService(
        retriever=Retriever(
            store=PgVectorStore(session),
            embedder=build_embedding_service(settings),
            config=RetrievalConfig.from_settings(settings),
        ),
        llm=build_llm_service(settings),
        conversations=ConversationRepository(session),
        assistant_name=settings.jarvis_name,
        company_name=settings.company_name,
        history_window=settings.history_window_messages,
        fast_model=settings.llm_fast_model,
    )

    by_id = {case["case_id"]: case for case in cases}
    scored = []

    print("\nGenerating answers...")
    for index, outcome in enumerate(outcomes, start=1):
        case = by_id[outcome.case_id]

        # Follow-ups are replayed as a real conversation, so the rewriting step
        # is exercised rather than bypassed.
        conversation_id = None
        result = None
        for turn in case.get("turns", [case["question"]]):
            result = await service.answer(turn, org_id=org_id, conversation_id=conversation_id)
            conversation_id = result.conversation_id

        refused = REFUSAL_MARKER in result.answer
        expected = case.get("expected_answer")
        matched = (
            not refused
            and expected is not None
            and any(part.strip().lower() in result.answer.lower() for part in expected.split("/"))
        )
        if case["kind"] == "unanswerable":
            matched = refused

        scored.append(
            replace(
                outcome,
                answer=result.answer,
                refused=refused,
                answer_matched=matched,
                citations_valid=all(s.page >= 1 for s in result.sources),
            )
        )
        if index % 10 == 0:
            print(f"  {index}/{len(outcomes)}")

    return scored


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval and answering.")
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN_SET)
    parser.add_argument(
        "--with-answers", action="store_true", help="Generate answers (needs an API key)."
    )
    parser.add_argument("--sweep", action="store_true", help="Sweep thresholds and compare.")
    parser.add_argument(
        "--floors",
        type=float,
        nargs="+",
        default=[0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.70],
    )
    parser.add_argument("--top-ks", dest="top_ks", type=int, nargs="+", default=[5])
    parser.add_argument("--dropoff", type=float, default=0.75)
    parser.add_argument("--save", action="store_true", help="Write a JSON result file.")
    args = parser.parse_args()

    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
