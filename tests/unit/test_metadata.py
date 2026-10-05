"""Document metadata parsed from the document's own header line.

Version and status drive the active-version filter, so getting them wrong is
not cosmetic -- it decides whether a superseded policy can be retrieved.
"""

from datetime import date

from app.models.db import DocStatus
from app.rag.metadata import parse_document_metadata

HEADER = (
    "Jarvis Financial Group\n"
    "Annual Leave Policy\n"
    "Version 2.0 — CURRENT\n"
    "Document type: HR Policy | Version: 2.0 | Effective date: 2026-01-01 | Status: ACTIVE\n"
    "1. Status of This Document"
)


def test_parses_every_field_from_the_header():
    meta = parse_document_metadata(HEADER, filename="Leave_Policy_v2.pdf")

    assert meta.doc_type == "HR Policy"
    assert meta.version == "2.0"
    assert meta.effective_date == date(2026, 1, 1)
    assert meta.doc_status is DocStatus.ACTIVE


def test_recognises_an_archived_document():
    text = HEADER.replace("Status: ACTIVE", "Status: ARCHIVED")

    assert parse_document_metadata(text, filename="x.pdf").doc_status is DocStatus.ARCHIVED


def test_title_comes_from_the_header_when_present():
    meta = parse_document_metadata(HEADER, filename="Leave_Policy_v2.pdf")

    assert meta.title == "Annual Leave Policy"


def test_title_falls_back_to_a_readable_filename():
    meta = parse_document_metadata("no useful header here.", filename="Employee_Handbook.pdf")

    assert meta.title == "Employee Handbook"


def test_missing_fields_are_none_rather_than_guessed():
    meta = parse_document_metadata("Just some prose.", filename="x.pdf")

    assert meta.version is None
    assert meta.effective_date is None
    assert meta.doc_type is None


def test_unparseable_date_does_not_raise():
    # A malformed date must not stop a document being indexed.
    text = HEADER.replace("Effective date: 2026-01-01", "Effective date: next January")

    meta = parse_document_metadata(text, filename="x.pdf")

    assert meta.effective_date is None
    assert meta.version == "2.0"


def test_unknown_status_defaults_to_active():
    # Defaulting to archived would make a freshly uploaded document invisible.
    text = HEADER.replace("Status: ACTIVE", "Status: WHATEVER")

    assert parse_document_metadata(text, filename="x.pdf").doc_status is DocStatus.ACTIVE
