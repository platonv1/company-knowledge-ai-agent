"""Faithfulness judging.

Retrieval metrics say whether the right passage was found. They say nothing
about whether the answer actually follows from it. A fluent, well-cited answer
that adds a detail the source does not contain passes every other metric in this
harness, so faithfulness is judged separately by a model reading the question,
the passages, and the answer together.

Two rules keep the number honest:

* An unparseable verdict is **unknown**, not a pass. A judge that replies with
  something unexpected must not quietly inflate the score.
* A refusal is **not judged**. It makes no claims, so there is nothing to
  verify; counting refusals as faithful would let the score be raised by
  refusing more often.
"""

import re

from app.core.logging import get_logger
from app.llm.base import ChatTurn, LLMService
from app.llm.prompts import REFUSAL_MARKER

logger = get_logger(__name__)

MAX_VERDICT_TOKENS = 200

JUDGE_SYSTEM_PROMPT = """You check whether an answer is supported by the source passages \
it was given.

You are not judging whether the answer is helpful, well written, or correct in the real
world. You are judging one thing: does every factual claim in the answer appear in, or
follow directly from, the passages provided?

Treat as UNSUPPORTED:
- any figure, date, name, or rule that is not in the passages
- a claim stated more strongly or more broadly than the passages state it
- a general fact about banking or employment that the passages do not contain

Treat as SUPPORTED:
- claims that restate or summarise the passages
- claims that combine two passages without adding anything new
- wording that differs from the passages while preserving their meaning

Reply with exactly one word on the first line, SUPPORTED or UNSUPPORTED, then one short
sentence of justification."""

# "unsupported" contains "supported", so the negative is matched first and both
# are anchored to a word boundary.
_UNSUPPORTED = re.compile(r"\bunsupported\b", re.IGNORECASE)
_SUPPORTED = re.compile(r"\bsupported\b", re.IGNORECASE)


def parse_verdict(text: str) -> bool | None:
    """True, False, or None when the judge said something unparseable."""
    if not text or not text.strip():
        return None
    if _UNSUPPORTED.search(text):
        return False
    if _SUPPORTED.search(text):
        return True
    logger.warning("Could not parse judge verdict: %r", text[:120])
    return None


def build_judge_prompt(question: str, context: str, answer: str) -> str:
    return f"""SOURCE PASSAGES
{context}

QUESTION
{question}

ANSWER TO CHECK
{answer}

VERDICT:"""


async def judge_answer(llm: LLMService, question: str, context: str, answer: str) -> bool | None:
    """Judge one answer. Returns None when the case is not judgeable."""
    if not context or not context.strip():
        return None
    if not answer or REFUSAL_MARKER in answer:
        return None

    try:
        verdict = await llm.complete(
            JUDGE_SYSTEM_PROMPT,
            [ChatTurn(role="user", content=build_judge_prompt(question, context, answer))],
            max_output_tokens=MAX_VERDICT_TOKENS,
        )
    except Exception as exc:  # noqa: BLE001 - one bad call must not end the run
        logger.warning("Judge call failed: %s", exc)
        return None

    return parse_verdict(verdict)
