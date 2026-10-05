"""Offline extractive answerer.

NOT a language model. It selects the sentences from the supplied context that
best overlap the question and cites their markers. It exists for two reasons:

1. The application, its demo, and its test suite run with no API key at all.
   Someone can clone the repository and see the whole pipeline work.
2. It gives the eval harness a non-LLM baseline. "The model scores X" means
   little without "sentence selection alone scores Y".

Its answers are blunt and it cannot paraphrase, aggregate across sources, or
handle a question whose wording differs from the document's. Those limits are
the point of comparison, so do not dress them up.
"""

import re

from app.llm.base import ChatTurn, LLMService
from app.llm.prompts import REFUSAL_TEXT

_SOURCE = re.compile(
    r'<source\s+id="(?P<marker>S\d+)"[^>]*>(?P<body>.*?)</source>',
    re.DOTALL | re.IGNORECASE,
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z0-9]+")

# Function words only, carrying no retrieval signal. An earlier version also
# listed "company", "employees" and
# "provide" -- which are the highest-signal words in a company knowledge base, so
# stripping them made "When was the company founded?" overlap on "founded" alone
# and fall below the threshold.
STOPWORDS = frozenset(
    """a an and are as at be been but by can did do does for from had has have how i if in
    into is it its may must not of on or our so than that the their them then there these
    they this to up was we were what when where which who why will with would you your""".split()
)

MAX_OVERLAP_REQUIRED = 2
MAX_SENTENCES = 3


def _required_overlap(question_tokens: set[str]) -> int:
    """How many words a sentence must share with the question.

    Proportional rather than fixed. A two-word question ("company founded")
    cannot clear a fixed threshold of two when the document says "Jarvis
    Financial Group" instead of "company", so a short question needs one strong
    match; a longer one still needs two, or every long question matches
    something.
    """
    if not question_tokens:
        return 1
    return max(1, min(MAX_OVERLAP_REQUIRED, (len(question_tokens) + 1) // 2))


# Light suffix stripping. Without it, "request" does not match "requests" and
# "notice ... request leave" misses "Requests must be submitted"; overlap counting
# has no morphology of its own. Crude on purpose -- a real stemmer is a
# dependency this baseline does not need.
_SUFFIXES = ("ements", "ement", "ing", "ies", "ied", "es", "ed", "s")


def _stem(word: str) -> str:
    for suffix in _SUFFIXES:
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _tokens(text: str) -> set[str]:
    return {_stem(w) for w in _WORD.findall(text.lower()) if w not in STOPWORDS and len(w) > 2}


def _extract_question(user_content: str) -> str:
    _, _, tail = user_content.rpartition("QUESTION\n")
    return (tail or user_content).strip()


class ExtractiveLLMService(LLMService):
    @property
    def model_name(self) -> str:
        return "extractive-offline"

    async def complete(
        self,
        system: str,
        turns: list[ChatTurn],
        *,
        model: str | None = None,
        max_output_tokens: int = 800,
        temperature: float = 0.0,
    ) -> str:
        content = turns[-1].content if turns else ""

        if "STANDALONE QUESTION" in content:
            return self._rewrite(content)
        return self._answer(content)

    # ---- answering ----

    def _answer(self, content: str) -> str:
        question = _extract_question(content)
        question_tokens = _tokens(question)
        required = _required_overlap(question_tokens)

        scored: list[tuple[int, str, str]] = []
        for match in _SOURCE.finditer(content):
            marker = match.group("marker")
            for sentence in _SENTENCE.split(match.group("body").strip()):
                sentence = " ".join(sentence.split())
                if not sentence:
                    continue
                overlap = len(question_tokens & _tokens(sentence))
                if overlap >= required:
                    scored.append((overlap, sentence, marker))

        if not scored:
            return REFUSAL_TEXT

        scored.sort(key=lambda row: row[0], reverse=True)

        selected: list[tuple[str, str]] = []
        seen: set[str] = set()
        for _, sentence, marker in scored[:MAX_SENTENCES]:
            if sentence in seen:
                continue
            seen.add(sentence)
            selected.append((sentence, marker))

        return " ".join(
            f"{sentence} [{marker}]" if not sentence.endswith(f"[{marker}]") else sentence
            for sentence, marker in selected
        )

    # ---- follow-up rewriting ----

    def _rewrite(self, content: str) -> str:
        """Concatenate the follow-up with the previous question's subject.

        It cannot paraphrase, so it appends the most recent user question's
        content words to the follow-up. That is enough for lexical retrieval to
        reach the right document, which is all the rewrite has to achieve.
        """
        follow_up = ""
        if "FOLLOW-UP QUESTION\n" in content:
            follow_up = content.split("FOLLOW-UP QUESTION\n", 1)[1]
            follow_up = follow_up.split("\n", 1)[0].strip()

        previous: list[str] = []
        for line in content.splitlines():
            if line.startswith("User:"):
                previous.append(line[len("User:") :].strip())

        if not previous:
            return follow_up or content.strip()

        subject = previous[-1].rstrip("?").strip()
        extra = [w for w in subject.split() if w.lower() not in _tokens(follow_up)]
        return f"{follow_up.rstrip('?')} {' '.join(extra)}".strip()


def build_extractive_service() -> ExtractiveLLMService:
    return ExtractiveLLMService()
