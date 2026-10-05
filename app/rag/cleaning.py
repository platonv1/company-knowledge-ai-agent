"""Text cleaning for extracted PDF content.

Two problems this solves, both of which quietly degrade retrieval rather than
causing visible errors:

* Running headers and footers. A footer on every page becomes the most
  repeated text in the document, so it dilutes every embedding and wastes
  context tokens on "Page 4 of 12".
* Extraction artefacts. Unmapped glyphs come through as "(cid:127)" and
  line-broken words come through hyphenated.
"""

import re
from collections import Counter

# Fraction of pages a line must appear on before it is treated as furniture
# rather than content.
REPEAT_THRESHOLD = 0.6
MIN_PAGES_FOR_REPEAT_DETECTION = 3

_CID = re.compile(r"\(cid:\d+\)")
_SOFT_HYPHEN = re.compile(r"(\w)-\s*\n\s*(\w)")
_SPACES = re.compile(r"[ \t ]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_SPACE = re.compile(r"[ \t]+\n")
# A line ENDING in "Page 4" or "Page 4 of 11" is a footer. Anchored at the end
# so "described on page 24 of the Handbook and must be followed" is untouched.
_PAGE_FOOTER = re.compile(r"\bpage\s+\d+(\s+of\s+\d+)?\s*$", re.IGNORECASE)


def clean_text(text: str) -> str:
    """Normalise one block of extracted text."""
    if not text:
        return ""

    text = _CID.sub("", text)
    # Rejoin words split across a line break before collapsing whitespace,
    # otherwise "compli- ance" survives as two tokens.
    text = _SOFT_HYPHEN.sub(r"\1\2", text)
    text = _SPACES.sub(" ", text)
    text = _TRAILING_SPACE.sub("\n", text)
    text = _BLANK_LINES.sub("\n\n", text)

    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def strip_repeated_lines(pages: list[str]) -> list[str]:
    """Remove running headers and footers.

    A line is furniture if it appears on at least `REPEAT_THRESHOLD` of pages.
    Below `MIN_PAGES_FOR_REPEAT_DETECTION` pages there is not enough evidence to
    distinguish furniture from content, so nothing is removed -- dropping real
    content is worse than keeping a footer.
    """
    pages = [_strip_page_footer(page) for page in pages]

    if len(pages) < MIN_PAGES_FOR_REPEAT_DETECTION:
        # Too few pages to tell furniture from content by repetition. The page
        # footer has already gone, which is the case that actually leaks into
        # answers from one- and two-page policies.
        return list(pages)

    counts: Counter[str] = Counter()
    for page in pages:
        # Count each distinct line once per page.
        for line in {ln.strip() for ln in page.split("\n") if ln.strip()}:
            counts[_normalise_for_comparison(line)] += 1

    minimum = max(2, int(len(pages) * REPEAT_THRESHOLD))
    furniture = {line for line, count in counts.items() if count >= minimum}

    cleaned: list[str] = []
    for page in pages:
        kept = [
            line
            for line in page.split("\n")
            if line.strip() and _normalise_for_comparison(line.strip()) not in furniture
        ]
        cleaned.append("\n".join(kept).strip())
    return cleaned


def _normalise_for_comparison(line: str) -> str:
    """Page numbers differ per page, so compare footers with digits masked."""
    return re.sub(r"\d+", "#", line.lower()).strip()


def _strip_page_footer(page: str) -> str:
    """Remove a trailing "Page N" line.

    Repetition detection needs several pages, so without this a one-page policy
    keeps its footer, and the footer then turns up quoted inside an answer.

    Only the final line is considered. A wider window starts eating real content
    on short pages, and keeping a footer is the cheaper mistake.
    """
    lines = page.split("\n")
    if lines and _PAGE_FOOTER.search(lines[-1].strip()):
        lines = lines[:-1]
    return "\n".join(lines).strip()
