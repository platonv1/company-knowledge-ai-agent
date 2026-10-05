"""PDF text and table extraction.

Design notes:

* Table regions are excluded from the page text and re-emitted as Markdown.
  Reading a table through `extract_text()` interleaves wrapped cells with the
  next column -- "Core banking" and "unavailable" end up either side of
  "15 minutes" -- so a fee schedule becomes unanswerable. Excluding the region
  and rebuilding it from `extract_tables()` keeps rows intact and stops the same
  content being embedded twice.
* A document with almost no extractable text raises rather than returning empty
  pages. Returning empty pages is the silent failure that makes a pipeline
  report a successful ingestion of a scanned handbook that nobody can query.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from app.core.logging import get_logger
from app.rag.cleaning import clean_text, strip_repeated_lines

logger = get_logger(__name__)

# A page with fewer than this many characters is treated as having no usable text.
MIN_CHARS_PER_PAGE = 50
# If more than this fraction of pages have no usable text, the document is a scan.
MAX_EMPTY_PAGE_RATIO = 0.3


class ExtractionError(Exception):
    """Base class for extraction failures."""


class ScannedDocumentError(ExtractionError):
    """The document carries no extractable text layer."""


@dataclass(frozen=True)
class ExtractedTable:
    page_number: int
    header: list[str]
    rows: list[list[str]]

    def to_markdown(self) -> str:
        """Pipe-delimited so row structure survives chunking and embedding."""
        widths = [self.header] + self.rows
        if not widths:
            return ""
        lines = [
            "| " + " | ".join(self.header) + " |",
            "| " + " | ".join("---" for _ in self.header) + " |",
        ]
        lines += ["| " + " | ".join(row) + " |" for row in self.rows]
        return "\n".join(lines)


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str
    tables: list[ExtractedTable] = field(default_factory=list)
    has_images: bool = False

    @property
    def combined_text(self) -> str:
        """Body text followed by any tables, as the chunker should see it."""
        parts = [self.text] if self.text.strip() else []
        parts += [table.to_markdown() for table in self.tables]
        return "\n\n".join(parts).strip()


@dataclass(frozen=True)
class ExtractedDocument:
    path: Path
    page_count: int
    pages: list[ExtractedPage]

    @property
    def tables(self) -> list[ExtractedTable]:
        return [table for page in self.pages for table in page.tables]


def _normalise_cell(cell: str | None) -> str:
    return clean_text(cell or "").replace("\n", " ").strip()


def _read_tables(page) -> list[ExtractedTable]:
    tables: list[ExtractedTable] = []
    for raw in page.extract_tables():
        rows = [[_normalise_cell(cell) for cell in row] for row in raw if row]
        rows = [row for row in rows if any(cell for cell in row)]
        if len(rows) < 2:
            # A single row is not a table worth structuring.
            continue
        tables.append(ExtractedTable(page_number=page.page_number, header=rows[0], rows=rows[1:]))
    return tables


def _text_outside_tables(page) -> str:
    """Extract page text with table regions removed."""
    table_boxes = [table.bbox for table in page.find_tables()]
    if not table_boxes:
        return page.extract_text() or ""

    def keep(obj) -> bool:
        centre_x = (obj["x0"] + obj["x1"]) / 2
        centre_y = (obj["top"] + obj["bottom"]) / 2
        return not any(
            x0 <= centre_x <= x1 and top <= centre_y <= bottom
            for x0, top, x1, bottom in table_boxes
        )

    return page.filter(keep).extract_text() or ""


def extract_document(path: str | Path) -> ExtractedDocument:
    """Extract one PDF into cleaned per-page text plus structured tables."""
    path = Path(path)

    raw_pages: list[str] = []
    page_tables: list[list[ExtractedTable]] = []
    page_has_images: list[bool] = []

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_tables.append(_read_tables(page))
            raw_pages.append(clean_text(_text_outside_tables(page)))
            page_has_images.append(bool(page.images))

    page_count = len(raw_pages)
    if page_count == 0:
        raise ExtractionError(f"{path.name} contains no pages.")

    _guard_against_scan(path, raw_pages, page_tables, page_has_images)

    # Footer removal needs all pages at once, so it runs after the per-page pass.
    bodies = strip_repeated_lines(raw_pages)

    pages = [
        ExtractedPage(
            page_number=index,
            text=body,
            tables=page_tables[index - 1],
            has_images=page_has_images[index - 1],
        )
        for index, body in enumerate(bodies, start=1)
    ]

    logger.info(
        "Extracted %s: %d pages, %d tables",
        path.name,
        page_count,
        sum(len(t) for t in page_tables),
    )
    return ExtractedDocument(path=path, page_count=page_count, pages=pages)


def _guard_against_scan(
    path: Path,
    raw_pages: list[str],
    page_tables: list[list[ExtractedTable]],
    page_has_images: list[bool],
) -> None:
    empty_pages = [
        index
        for index, text in enumerate(raw_pages, start=1)
        if len(text) < MIN_CHARS_PER_PAGE and not page_tables[index - 1]
    ]
    ratio = len(empty_pages) / len(raw_pages)
    if ratio <= MAX_EMPTY_PAGE_RATIO:
        return

    imaged = sum(1 for index in empty_pages if page_has_images[index - 1])
    detail = (
        f"{len(empty_pages)} of {len(raw_pages)} pages have no extractable text"
        f" ({imaged} contain images)"
    )
    raise ScannedDocumentError(
        f"{path.name} appears to be a scan: {detail}. "
        "OCR is not supported, so this document cannot be indexed."
    )
