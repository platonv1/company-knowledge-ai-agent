"""Eval metric definitions.

Kept as pure functions so each metric has one fixed meaning. The numbers that
end up in the README are only comparable across runs if the definitions do not
drift, and a silently redefined metric is worse than no metric at all.

Metrics, and why each is here:

* **page hit** -- the expected document AND page were retrieved. The stricter
  of the two retrieval metrics, because a right answer with a wrong page is
  still a citation failure.
* **document hit** -- the expected document was retrieved, page ignored. Useful
  for separating "retrieval missed" from "chunking split the fact badly".
* **refusal accuracy** -- unanswerable questions where nothing cleared the gate.
* **over-refusal** -- answerable questions where nothing cleared the gate. The
  failure a too-high floor introduces. Refusal accuracy alone is gameable by
  refusing everything, so the two are always reported together.
* **version leak** -- an archived document appeared in the results at all.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RetrievedChunk:
    document: str
    page_start: int
    page_end: int
    score: float

    def covers(self, page: int) -> bool:
        return self.page_start <= page <= self.page_end


@dataclass(frozen=True)
class Outcome:
    case_id: str
    kind: str  # "fact" | "unanswerable" | "followup"
    question: str
    category: str
    expected_document: str | None
    expected_page: int | None
    retrieved: list[RetrievedChunk] = field(default_factory=list)
    # Populated only when the eval runs with a live model.
    answer: str | None = None
    answer_matched: bool | None = None
    refused: bool | None = None
    citations_valid: bool | None = None
    faithful: bool | None = None

    @property
    def retrieved_nothing(self) -> bool:
        return not self.retrieved


def document_hit(outcome: Outcome) -> bool:
    if not outcome.expected_document:
        return False
    return any(c.document == outcome.expected_document for c in outcome.retrieved)


def page_hit(outcome: Outcome) -> bool:
    if not outcome.expected_document or outcome.expected_page is None:
        return False
    return any(
        c.document == outcome.expected_document and c.covers(outcome.expected_page)
        for c in outcome.retrieved
    )


def top_document_correct(outcome: Outcome) -> bool:
    if not outcome.retrieved or not outcome.expected_document:
        return False
    return outcome.retrieved[0].document == outcome.expected_document


def version_leak(outcome: Outcome, archived: set[str]) -> bool:
    return any(c.document in archived for c in outcome.retrieved)


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


@dataclass(frozen=True)
class EvalSummary:
    answerable: int
    unanswerable: int
    page_hits: int
    document_hits: int
    top1_correct: int
    over_refusals: int
    correct_refusals: int
    over_retrieval: int
    version_leaks: int
    answers_matched: int | None = None
    citations_valid: int | None = None
    faithful: int | None = None
    answered: int = 0
    # Unanswerable cases that produced a refusal, whether the gate stopped them
    # or the answerer did.
    refused_end_to_end: int | None = None
    unanswerable_answered: int = 0
    # Cases the judge actually assessed. Refusals make no claims and failed
    # judge calls have no verdict, so neither belongs in the denominator.
    judged: int = 0

    @property
    def page_hit_rate(self) -> float:
        return _rate(self.page_hits, self.answerable)

    @property
    def document_hit_rate(self) -> float:
        return _rate(self.document_hits, self.answerable)

    @property
    def top1_rate(self) -> float:
        return _rate(self.top1_correct, self.answerable)

    @property
    def refusal_accuracy(self) -> float:
        return _rate(self.correct_refusals, self.unanswerable)

    @property
    def over_refusal_rate(self) -> float:
        return _rate(self.over_refusals, self.answerable)

    @property
    def end_to_end_refusal_accuracy(self) -> float | None:
        """Refusal accuracy for the whole pipeline, not just the gate.

        The gate is the first filter and the answerer is the second, so
        `refusal_accuracy` alone understates the system.
        """
        if self.refused_end_to_end is None:
            return None
        return _rate(self.refused_end_to_end, self.unanswerable_answered)

    @property
    def answer_match_rate(self) -> float | None:
        if self.answers_matched is None:
            return None
        return _rate(self.answers_matched, self.answered)

    @property
    def faithfulness_rate(self) -> float | None:
        if self.faithful is None or self.judged == 0:
            return None
        return _rate(self.faithful, self.judged)


def summarise(outcomes: list[Outcome], archived: set[str]) -> EvalSummary:
    answerable = [o for o in outcomes if o.kind != "unanswerable"]
    unanswerable = [o for o in outcomes if o.kind == "unanswerable"]
    scored = [o for o in outcomes if o.answer is not None]
    unanswerable_scored = [o for o in unanswerable if o.answer is not None]
    judged = [o for o in outcomes if o.faithful is not None]

    return EvalSummary(
        answerable=len(answerable),
        unanswerable=len(unanswerable),
        page_hits=sum(1 for o in answerable if page_hit(o)),
        document_hits=sum(1 for o in answerable if document_hit(o)),
        top1_correct=sum(1 for o in answerable if top_document_correct(o)),
        over_refusals=sum(1 for o in answerable if o.retrieved_nothing),
        correct_refusals=sum(1 for o in unanswerable if o.retrieved_nothing),
        over_retrieval=sum(1 for o in unanswerable if not o.retrieved_nothing),
        version_leaks=sum(1 for o in outcomes if version_leak(o, archived)),
        answered=len(scored),
        unanswerable_answered=len(unanswerable_scored),
        refused_end_to_end=(
            sum(1 for o in unanswerable_scored if o.refused) if unanswerable_scored else None
        ),
        answers_matched=(sum(1 for o in scored if o.answer_matched) if scored else None),
        citations_valid=(sum(1 for o in scored if o.citations_valid) if scored else None),
        judged=len(judged),
        faithful=sum(1 for o in judged if o.faithful) if judged else None,
    )
