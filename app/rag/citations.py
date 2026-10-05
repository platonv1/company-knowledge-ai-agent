"""Citation resolution.

The model writes markers; this module turns them into citations. A marker the
backend did not supply is stripped from the answer and reported, so a
hallucinated citation cannot reach the user. That is the whole reason the model
is never asked to write "page 24" itself: a plausible wrong page number is
indistinguishable from a right one to the reader.
"""

import re
import uuid
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.repositories.vector_store import SearchResult

logger = get_logger(__name__)

# Matches [S1] and [S1, S2] -- models produce both.
_MARKER_GROUP = re.compile(r"\[\s*(S\d+(?:\s*,\s*S\d+)*)\s*\]", re.IGNORECASE)
_MARKER = re.compile(r"S\d+", re.IGNORECASE)


@dataclass(frozen=True)
class Citation:
    marker: str
    chunk_id: uuid.UUID
    document: str
    document_title: str
    page: int
    page_end: int
    section: str | None
    version: str | None

    @property
    def page_label(self) -> str:
        return str(self.page) if self.page == self.page_end else f"{self.page}-{self.page_end}"


@dataclass(frozen=True)
class ResolvedAnswer:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    invented_markers: list[str] = field(default_factory=list)


def _to_citation(marker: str, result: SearchResult) -> Citation:
    return Citation(
        marker=marker,
        chunk_id=result.chunk_id,
        document=result.document_filename,
        document_title=result.document_title,
        page=result.page_start,
        page_end=result.page_end,
        section=result.section_path,
        version=result.document_version,
    )


def resolve_citations(answer: str, source_map: dict[str, SearchResult]) -> ResolvedAnswer:
    """Map the markers in an answer back to the chunks that were supplied."""
    citations: list[Citation] = []
    seen: set[str] = set()
    invented: list[str] = []

    for group in _MARKER_GROUP.finditer(answer):
        for raw in _MARKER.findall(group.group(1)):
            marker = raw.upper()
            if marker in seen:
                continue
            seen.add(marker)

            result = source_map.get(marker)
            if result is None:
                invented.append(marker)
                continue
            citations.append(_to_citation(marker, result))

    cleaned = answer
    if invented:
        logger.warning(
            "Model cited %d marker(s) that were not supplied: %s", len(invented), invented
        )
        cleaned = _strip_invented(answer, set(invented))

    return ResolvedAnswer(answer=cleaned.strip(), citations=citations, invented_markers=invented)


def _strip_invented(answer: str, invented: set[str]) -> str:
    """Remove unknown markers, keeping any valid markers in the same group."""

    def replace(match: re.Match[str]) -> str:
        kept = [m.upper() for m in _MARKER.findall(match.group(1)) if m.upper() not in invented]
        if not kept:
            return ""
        return "[" + ", ".join(kept) + "]"

    # Collapse the double space left behind by a removed marker.
    return re.sub(r" {2,}", " ", _MARKER_GROUP.sub(replace, answer))
