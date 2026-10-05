"""Schema for the generated demo corpus.

A `Fact` records a question whose answer is known by construction, plus an
`anchor`: a distinctive phrase that appears in the rendered text. Page numbers
are resolved by searching the generated PDF for that anchor, so the golden set
never contains a hand-typed page number that could silently drift.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Table:
    caption: str
    columns: list[str]
    rows: list[list[str]]


@dataclass(frozen=True)
class Section:
    number: str
    heading: str
    paragraphs: list[str] = field(default_factory=list)
    table: Table | None = None
    bullets: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Document:
    filename: str
    title: str
    doc_type: str
    sections: list[Section]
    version: str | None = None
    effective_date: str | None = None
    doc_status: str = "active"
    subtitle: str = ""


@dataclass(frozen=True)
class Fact:
    id: str
    question: str
    answer: str
    anchor: str
    document: str
    category: str = "direct"
    notes: str = ""


@dataclass(frozen=True)
class Unanswerable:
    id: str
    question: str
    reason: str


@dataclass(frozen=True)
class Followup:
    """A multi-turn case. The second question is unanswerable in isolation, so it
    only passes if query contextualisation rewrote it against the first turn."""

    id: str
    turns: list[str]
    answer_contains: list[str]
    document: str
