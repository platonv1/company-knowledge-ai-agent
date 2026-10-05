"""The corpus generator is tested by reading back what it rendered.

Asserting on the in-memory content objects would prove nothing: the thing that
matters is whether pdfplumber can recover the facts from the actual PDF bytes,
including from tables.
"""

import re

import pdfplumber
import pytest
import yaml

from scripts.corpus_content import FACTS, SCANNED_DOCUMENT_FILENAME, TEXT_DOCUMENTS
from scripts.generate_corpus import generate_corpus


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    out = tmp_path_factory.mktemp("corpus")
    result = generate_corpus(out, facts_path=out / "corpus_facts.yaml")
    return result


def test_generates_one_pdf_per_document_plus_the_scanned_one(corpus):
    names = {d.filename for d in corpus.documents}
    assert names == {d.filename for d in TEXT_DOCUMENTS} | {SCANNED_DOCUMENT_FILENAME}


def test_every_fact_anchor_is_found_on_a_real_page(corpus):
    unresolved = [f.id for f in corpus.facts if f.page is None]
    assert unresolved == [], f"anchors not found in the rendered PDFs: {unresolved}"
    assert all(f.page >= 1 for f in corpus.facts)
    assert len(corpus.facts) == len(FACTS)


def test_resolved_page_actually_contains_the_anchor(corpus):
    # Guards against an off-by-one between reportlab page order and pdfplumber indexing.
    by_name = {d.filename: d for d in corpus.documents}
    for fact in corpus.facts:
        path = by_name[fact.document].path
        with pdfplumber.open(path) as pdf:
            page_text = normalise(pdf.pages[fact.page - 1].extract_text() or "")
        assert normalise(fact.anchor) in page_text, (
            f"{fact.id}: anchor not on resolved page {fact.page} of {fact.document}"
        )


def test_scanned_notice_has_no_extractable_text(corpus):
    # This is the whole point of the file: text extraction must come back empty so
    # ingestion has something to detect.
    path = next(d.path for d in corpus.documents if d.filename == SCANNED_DOCUMENT_FILENAME)
    with pdfplumber.open(path) as pdf:
        extracted = "".join(page.extract_text() or "" for page in pdf.pages)
    assert len(extracted.strip()) < 10


def test_fee_table_survives_extraction(corpus):
    path = next(d.path for d in corpus.documents if d.filename == "Products_and_Services.pdf")
    with pdfplumber.open(path) as pdf:
        tables = [t for page in pdf.pages for t in page.extract_tables()]
    flattened = [
        normalise(" ".join(cell or "" for cell in row)) for table in tables for row in table
    ]
    assert any("Domestic wire transfer" in row and "15.00" in row for row in flattened)
    assert any("International wire transfer" in row and "35.00" in row for row in flattened)


def test_leave_policy_versions_disagree_as_designed(corpus):
    # If these ever agree, the version trap stops testing anything.
    def text_of(filename: str) -> str:
        path = next(d.path for d in corpus.documents if d.filename == filename)
        with pdfplumber.open(path) as pdf:
            return normalise(" ".join(page.extract_text() or "" for page in pdf.pages))

    assert "15 days of paid annual leave" in text_of("Leave_Policy_v2.pdf")
    assert "12 days of paid annual leave" in text_of("Leave_Policy_v1.pdf")


def test_facts_file_records_resolved_pages_and_statuses(corpus):
    data = yaml.safe_load((corpus.facts_path).read_text())

    assert data["company"] == "Jarvis Financial Group"
    leave = next(f for f in data["facts"] if f["id"] == "annual_leave_days")
    assert leave["answer"] == "15 days"
    assert leave["document"] == "Leave_Policy_v2.pdf"
    assert isinstance(leave["page"], int)

    archived = next(d for d in data["documents"] if d["filename"] == "Leave_Policy_v1.pdf")
    assert archived["doc_status"] == "archived"

    assert len(data["unanswerable"]) >= 5
    assert len(data["followups"]) >= 3
