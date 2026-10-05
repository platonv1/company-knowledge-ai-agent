"""Extraction tested against real generated PDFs.

The corpus is generated into a temp dir rather than read from documents/, so the
suite does not depend on a gitignored artefact being present.
"""

import pytest

from app.rag.extraction import ScannedDocumentError, extract_document
from scripts.generate_corpus import generate_corpus


@pytest.fixture(scope="module")
def corpus_paths(tmp_path_factory):
    out = tmp_path_factory.mktemp("extract_corpus")
    result = generate_corpus(out, facts_path=out / "facts.yaml")
    return {d.filename: d.path for d in result.documents}


def test_extracts_one_entry_per_page_numbered_from_one(corpus_paths):
    doc = extract_document(corpus_paths["Employee_Handbook.pdf"])

    assert doc.page_count == len(doc.pages) == 3
    assert [p.page_number for p in doc.pages] == [1, 2, 3]


def test_running_footer_is_removed_from_page_text(corpus_paths):
    doc = extract_document(corpus_paths["Employee_Handbook.pdf"])

    body = "\n".join(p.text for p in doc.pages)
    assert "Employee Handbook" in body  # the heading survives
    assert "Page 2" not in body
    assert body.count("Jarvis Financial Group — Employee Handbook") == 0


def test_tables_are_extracted_as_structured_markdown(corpus_paths):
    doc = extract_document(corpus_paths["Products_and_Services.pdf"])

    markdown = "\n".join(t.to_markdown() for p in doc.pages for t in p.tables)
    assert "| Domestic wire transfer | 15.00 |" in markdown
    assert "| International wire transfer | 35.00 |" in markdown


def test_table_text_is_not_duplicated_in_the_page_body(corpus_paths):
    # The body text and the markdown table must not both carry the fee rows, or
    # every table chunk is embedded twice and retrieval returns near-duplicates.
    doc = extract_document(corpus_paths["Products_and_Services.pdf"])

    body = "\n".join(p.text for p in doc.pages)
    assert "Domestic wire transfer" not in body


def test_wrapped_table_cell_is_recovered_intact(corpus_paths):
    # "Core banking unavailable" wraps inside its cell; page text splits it
    # across columns, extract_tables must put it back together.
    doc = extract_document(corpus_paths["IT_Acceptable_Use_Policy.pdf"])

    cells = [cell for p in doc.pages for t in p.tables for row in t.rows for cell in row]
    assert any("Core banking unavailable" in cell for cell in cells)


def test_scanned_document_raises_rather_than_returning_empty_text(corpus_paths):
    # The failure this prevents: indexing empty chunks and reporting success.
    with pytest.raises(ScannedDocumentError) as exc:
        extract_document(corpus_paths["Scanned_Notice.pdf"])

    assert "scan" in str(exc.value).lower()


def test_text_documents_all_extract_without_error(corpus_paths):
    for filename, path in corpus_paths.items():
        if filename == "Scanned_Notice.pdf":
            continue
        doc = extract_document(path)
        assert doc.pages, f"{filename} produced no pages"
        assert any(p.text.strip() for p in doc.pages), f"{filename} produced no text"
