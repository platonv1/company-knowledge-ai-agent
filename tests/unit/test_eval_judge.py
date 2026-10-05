"""The faithfulness judge.

Measures whether an answer's claims are actually supported by the passages it
was given, which is the metric that catches a plausible, well-cited answer that
the documents do not support.

The judge is itself a model, so it can be wrong or reply with something
unparseable. An unparseable verdict must come back as None -- unknown -- and be
excluded from the score, never silently counted as a pass.
"""

from app.llm.base import ScriptedLLMService
from scripts.eval_judge import judge_answer, parse_verdict

CONTEXT = """<source id="S1" document="Leave_Policy_v2.pdf" page="2" section="2. Entitlement">
Full-time employees are entitled to 15 days of paid annual leave per calendar year.
</source>"""


def test_parses_a_supported_verdict():
    assert parse_verdict("SUPPORTED") is True


def test_parses_an_unsupported_verdict():
    assert parse_verdict("UNSUPPORTED") is False


def test_parsing_ignores_case_and_surrounding_prose():
    assert parse_verdict("Verdict: supported. Every claim appears in S1.") is True
    assert parse_verdict("unsupported - the 20 day figure is not in the sources") is False


def test_unsupported_is_not_mistaken_for_supported():
    # "unsupported" contains "supported", so naive matching inverts the verdict.
    assert parse_verdict("UNSUPPORTED: invented") is False


def test_an_unparseable_verdict_is_unknown_rather_than_a_pass():
    assert parse_verdict("I'm not sure how to assess this.") is None
    assert parse_verdict("") is None


async def test_judges_a_supported_answer_as_faithful():
    llm = ScriptedLLMService(responses=["SUPPORTED"])

    verdict = await judge_answer(
        llm, "How many leave days?", CONTEXT, "Employees receive 15 days. [S1]"
    )

    assert verdict is True


async def test_judges_an_unsupported_answer_as_unfaithful():
    llm = ScriptedLLMService(responses=["UNSUPPORTED"])

    verdict = await judge_answer(
        llm, "How many leave days?", CONTEXT, "Employees receive 20 days. [S1]"
    )

    assert verdict is False


async def test_the_judge_sees_the_question_context_and_answer():
    llm = ScriptedLLMService(responses=["SUPPORTED"])

    await judge_answer(llm, "How many leave days?", CONTEXT, "Employees receive 15 days.")

    sent = llm.calls[0]["turns"][0].content
    assert "How many leave days?" in sent
    assert "15 days of paid annual leave" in sent  # the context
    assert "Employees receive 15 days." in sent  # the answer


async def test_a_refusal_is_not_judged():
    """A refusal makes no claims, so there is nothing to verify.

    Counting it as faithful would inflate the score simply by refusing more.
    """
    llm = ScriptedLLMService(responses=[])

    verdict = await judge_answer(
        llm,
        "What is the dividend policy?",
        CONTEXT,
        "I couldn't find that information in the company's current knowledge base.",
    )

    assert verdict is None
    assert llm.call_count == 0


async def test_an_answer_without_context_is_not_judged():
    llm = ScriptedLLMService(responses=[])

    assert await judge_answer(llm, "q", "", "some answer") is None
    assert llm.call_count == 0


async def test_a_judge_failure_is_unknown_rather_than_fatal():
    # One bad judge call must not abort a 72-case evaluation run.
    llm = ScriptedLLMService(responses=[])  # raises when asked

    verdict = await judge_answer(llm, "q", CONTEXT, "a real answer with claims")

    assert verdict is None
