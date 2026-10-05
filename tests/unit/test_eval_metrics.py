"""Eval metric definitions.

These are pure functions so the definitions are pinned. A metric whose meaning
drifts silently is worse than no metric: the numbers in the README stop being
comparable across runs.
"""

from scripts.eval_core import (
    Outcome,
    RetrievedChunk,
    document_hit,
    page_hit,
    summarise,
    version_leak,
)


def retrieved(document: str, page_start: int = 2, page_end: int = 2) -> RetrievedChunk:
    return RetrievedChunk(document=document, page_start=page_start, page_end=page_end, score=0.6)


def outcome(
    *,
    case_id: str = "c1",
    kind: str = "fact",
    expected_document: str | None = "Leave_Policy_v2.pdf",
    expected_page: int | None = 2,
    chunks: list[RetrievedChunk] | None = None,
    category: str = "direct",
) -> Outcome:
    return Outcome(
        case_id=case_id,
        kind=kind,
        question="q",
        category=category,
        expected_document=expected_document,
        expected_page=expected_page,
        retrieved=chunks if chunks is not None else [retrieved("Leave_Policy_v2.pdf")],
    )


def test_page_hit_requires_the_right_document_and_page():
    assert page_hit(outcome()) is True


def test_page_hit_fails_when_the_page_is_wrong():
    # A correct document with the wrong page is a citation failure.
    assert page_hit(outcome(chunks=[retrieved("Leave_Policy_v2.pdf", 7, 7)])) is False


def test_page_hit_accepts_a_chunk_spanning_the_expected_page():
    assert page_hit(outcome(chunks=[retrieved("Leave_Policy_v2.pdf", 1, 3)])) is True


def test_page_hit_fails_when_the_document_is_wrong():
    assert page_hit(outcome(chunks=[retrieved("Leave_Policy_v1.pdf", 2, 2)])) is False


def test_document_hit_ignores_the_page():
    out = outcome(chunks=[retrieved("Leave_Policy_v2.pdf", 9, 9)])

    assert document_hit(out) is True
    assert page_hit(out) is False


def test_nothing_retrieved_is_not_a_hit():
    out = outcome(chunks=[])

    assert document_hit(out) is False
    assert page_hit(out) is False


def test_version_leak_detects_a_superseded_document_in_the_results():
    out = outcome(
        chunks=[retrieved("Leave_Policy_v2.pdf"), retrieved("Leave_Policy_v1.pdf")],
        category="version_trap",
    )

    assert version_leak(out, archived={"Leave_Policy_v1.pdf"}) is True


def test_no_version_leak_when_only_active_documents_are_returned():
    assert version_leak(outcome(), archived={"Leave_Policy_v1.pdf"}) is False


def test_summary_counts_hits_and_refusals():
    outcomes = [
        outcome(case_id="a"),
        outcome(case_id="b", chunks=[retrieved("Wrong.pdf")]),
        outcome(case_id="c", kind="unanswerable", expected_document=None, chunks=[]),
        outcome(case_id="d", kind="unanswerable", expected_document=None),
    ]

    summary = summarise(outcomes, archived=set())

    assert summary.answerable == 2
    assert summary.page_hits == 1
    assert summary.unanswerable == 2
    # One correctly retrieved nothing; the other retrieved something it should not.
    assert summary.correct_refusals == 1
    assert summary.over_retrieval == 1


def test_summary_reports_rates_as_fractions():
    outcomes = [outcome(case_id="a"), outcome(case_id="b", chunks=[retrieved("Wrong.pdf")])]

    summary = summarise(outcomes, archived=set())

    assert summary.page_hit_rate == 0.5


def test_summary_handles_an_empty_run_without_dividing_by_zero():
    summary = summarise([], archived=set())

    assert summary.page_hit_rate == 0.0
    assert summary.refusal_accuracy == 0.0


def test_summary_tracks_over_refusal_on_answerable_questions():
    # Refusing a question the corpus answers is the failure mode a high floor
    # introduces, so it must be measured alongside refusal accuracy.
    outcomes = [outcome(case_id="a", chunks=[]), outcome(case_id="b")]

    summary = summarise(outcomes, archived=set())

    assert summary.over_refusals == 1
    assert summary.over_refusal_rate == 0.5


def test_end_to_end_refusal_is_measured_separately_from_the_gate():
    """The gate is only the first filter; the answerer refuses too.

    Gate-level refusal accuracy therefore understates the system. A case where
    chunks cleared the gate but the answer was a refusal is a correct refusal
    end to end, and must be counted as one.
    """
    outcomes = [
        # Cleared the gate, but the answer refused -> correct end to end.
        Outcome(
            case_id="a",
            kind="unanswerable",
            question="q",
            category="unanswerable",
            expected_document=None,
            expected_page=None,
            retrieved=[retrieved("Handbook.pdf")],
            answer="I couldn't find that information...",
            refused=True,
        ),
        # Cleared the gate and answered anyway -> wrong.
        Outcome(
            case_id="b",
            kind="unanswerable",
            question="q",
            category="unanswerable",
            expected_document=None,
            expected_page=None,
            retrieved=[retrieved("Handbook.pdf")],
            answer="Yes, the company offers that.",
            refused=False,
        ),
    ]

    summary = summarise(outcomes, archived=set())

    assert summary.refusal_accuracy == 0.0  # neither was stopped by the gate
    assert summary.end_to_end_refusal_accuracy == 0.5


def test_end_to_end_refusal_is_none_when_no_answers_were_generated():
    summary = summarise([outcome(case_id="a", kind="unanswerable", expected_document=None)], set())

    assert summary.end_to_end_refusal_accuracy is None
