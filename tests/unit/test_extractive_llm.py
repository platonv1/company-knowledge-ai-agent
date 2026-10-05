"""The offline extractive provider.

It exists so the application runs, and can be demonstrated, with no API key,
and so the eval has a non-LLM baseline to compare against. It is not a language
model: it selects sentences from the supplied context and cites them.

Its contract matters because the rest of the pipeline depends on it: it must
cite real markers and must refuse rather than invent.
"""

from app.llm.base import ChatTurn
from app.llm.extractive import ExtractiveLLMService
from app.llm.prompts import REFUSAL_MARKER, answer_prompt

CONTEXT = """<source id="S1" document="Leave_Policy_v2.pdf" page="2" section="2. Entitlement">
Full-time employees are entitled to 15 days of paid annual leave per calendar year.
Part-time employees receive a pro rata entitlement calculated on contracted hours.
</source>

<source id="S2" document="HR_Policy.pdf" page="1" section="3. Leave Application">
Requests must be submitted at least 14 calendar days before the first day of leave.
</source>"""


async def ask(question: str, context: str = CONTEXT) -> str:
    service = ExtractiveLLMService()
    return await service.complete(
        "system", [ChatTurn(role="user", content=answer_prompt(context, question))]
    )


async def test_selects_the_sentence_that_answers_the_question():
    answer = await ask("How many annual leave days do employees get?")

    assert "15 days of paid annual leave" in answer


async def test_cites_the_marker_of_the_source_it_used():
    answer = await ask("How many annual leave days do employees get?")

    assert "[S1]" in answer


async def test_never_cites_a_marker_that_was_not_supplied():
    answer = await ask("How many annual leave days do employees get?")

    for marker in ("[S3]", "[S4]", "[S9]"):
        assert marker not in answer


async def test_picks_the_right_source_when_several_are_present():
    answer = await ask("How much notice is needed to request leave?")

    assert "14 calendar days" in answer
    assert "[S2]" in answer


async def test_refuses_when_the_context_is_empty():
    answer = await ask("What is the dividend policy?", context="")

    assert REFUSAL_MARKER in answer


async def test_refuses_when_no_sentence_overlaps_the_question():
    answer = await ask("What is the maximum altitude of a commercial aircraft?")

    assert REFUSAL_MARKER in answer


async def test_rewrites_a_follow_up_using_the_conversation():
    # The contextualiser path must also work offline, or follow-ups break in the
    # keyless demo.
    service = ExtractiveLLMService()

    rewritten = await service.complete(
        "You rewrite a follow-up question into a standalone question.",
        [
            ChatTurn(
                role="user",
                content=(
                    "CONVERSATION SO FAR\nUser: What is the annual leave policy?\n"
                    "Assistant: The company provides several categories of leave.\n\n"
                    "FOLLOW-UP QUESTION\nHow many days?\n\nSTANDALONE QUESTION:"
                ),
            )
        ],
    )

    # It cannot paraphrase, so it concatenates: enough for lexical retrieval to
    # reach the right document, which is all the rewrite needs to achieve.
    assert "days" in rewritten.lower()
    assert "annual leave" in rewritten.lower()


HISTORY_CONTEXT = """<source id="S1" document="Company_Profile.pdf" page="1" section="2. History">
Jarvis Financial Group was founded in 1985 by Eleanor M. Jarvis, who established the
original Northgate Savings and Loan office with eleven members of staff.
</source>"""


async def test_a_short_question_still_matches_on_one_strong_word():
    """A fixed overlap of two is too strict for a short question.

    "When was the company founded?" reduces to two content words, and the
    document says "Jarvis Financial Group" rather than "company" -- so a fixed
    threshold of two refuses even though the answer is right there.
    """
    answer = await ask("When was the company founded?", context=HISTORY_CONTEXT)

    assert "1985" in answer
    assert "[S1]" in answer


async def test_a_longer_question_still_requires_more_than_one_word_in_common():
    # The proportional threshold must not collapse into "any single word", or
    # every long question matches something.
    answer = await ask(
        "What are the wire transfer fees charged on international payments?",
        context=HISTORY_CONTEXT,
    )

    assert REFUSAL_MARKER in answer
