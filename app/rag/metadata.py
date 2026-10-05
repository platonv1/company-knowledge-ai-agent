"""Document metadata read from the document's own header.

Controlled documents in this corpus carry a header line:

    Document type: HR Policy | Version: 2.0 | Effective date: 2026-01-01 | Status: ACTIVE

Reading it means version and status come from the document rather than from
whoever happened to upload it. An admin override is still possible, but the
default is the document's own statement about itself.

Unparseable values become None rather than a guess: a wrong effective date
would silently reorder which policy counts as current.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime

from app.core.logging import get_logger
from app.models.db import DocStatus

logger = get_logger(__name__)

# Only the opening of a document is searched, so a later mention of "Version:"
# in body text cannot override the header.
HEADER_SEARCH_LINES = 12

_DOC_TYPE = re.compile(r"Document type:\s*([^|\n]+)", re.IGNORECASE)
_VERSION = re.compile(r"Version:\s*([^|\n]+)", re.IGNORECASE)
_EFFECTIVE = re.compile(r"Effective date:\s*([^|\n]+)", re.IGNORECASE)
_STATUS = re.compile(r"Status:\s*([A-Za-z]+)", re.IGNORECASE)

DATE_FORMATS = ("%Y-%m-%d", "%d %B %Y", "%d/%m/%Y", "%B %Y")


@dataclass(frozen=True)
class DocumentMetadata:
    title: str
    doc_type: str | None = None
    version: str | None = None
    effective_date: date | None = None
    doc_status: DocStatus = DocStatus.ACTIVE


def _title_from_filename(filename: str) -> str:
    stem = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)
    return stem.replace("_", " ").strip()


def _parse_date(raw: str) -> date | None:
    candidate = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    logger.warning("Could not parse effective date %r; leaving it unset.", candidate)
    return None


def _parse_title(lines: list[str], filename: str) -> str:
    """The title is the first substantial line that is not boilerplate."""
    fallback = _title_from_filename(filename)
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith(("jarvis financial group", "document type:", "version ")):
            continue
        if re.match(r"^\d+(\.\d+)*\.?\s", stripped):  # already into numbered sections
            break
        # A title is a short phrase, not a sentence. Requiring no terminal
        # punctuation stops ordinary prose being promoted to the title when a
        # document has no header block.
        if 3 <= len(stripped) <= 120 and len(stripped.split()) <= 12:
            if not stripped.endswith((".", "!", "?", ":", ";", ",")):
                return stripped
    return fallback


def parse_document_metadata(first_page_text: str, filename: str) -> DocumentMetadata:
    """Derive metadata from the opening of a document."""
    lines = first_page_text.split("\n")[:HEADER_SEARCH_LINES]
    header = "\n".join(lines)

    doc_type_match = _DOC_TYPE.search(header)
    version_match = _VERSION.search(header)
    effective_match = _EFFECTIVE.search(header)
    status_match = _STATUS.search(header)

    status = DocStatus.ACTIVE
    if status_match:
        raw_status = status_match.group(1).strip().lower()
        if raw_status in {s.value for s in DocStatus}:
            status = DocStatus(raw_status)
        else:
            # Defaulting to ACTIVE on an unrecognised value is deliberate:
            # defaulting to ARCHIVED would make the document unretrievable.
            logger.warning("Unrecognised document status %r; treating as active.", raw_status)

    return DocumentMetadata(
        title=_parse_title(lines, filename),
        doc_type=doc_type_match.group(1).strip() if doc_type_match else None,
        version=version_match.group(1).strip() if version_match else None,
        effective_date=_parse_date(effective_match.group(1)) if effective_match else None,
        doc_status=status,
    )
