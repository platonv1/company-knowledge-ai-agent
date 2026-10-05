"""Chunking rules.

Built on synthetic ExtractedDocuments so each rule is tested in isolation; the
real-corpus behaviour is covered in tests/integration/test_chunking_corpus.py.
"""

from app.rag.chunking import ChunkConfig, chunk_document
from app.rag.extraction import ExtractedDocument, ExtractedPage, ExtractedTable

CONFIG = ChunkConfig(target_tokens=120, max_tokens=180, overlap_ratio=0.1)


def make_document(pages: list[ExtractedPage]) -> ExtractedDocument:
    return ExtractedDocument(path="synthetic.pdf", page_count=len(pages), pages=pages)


def sentence(word: str, times: int) -> str:
    return " ".join([word] * times) + "."


def test_numbered_heading_becomes_the_section_path():
    doc = make_document(
        [ExtractedPage(1, "1. Annual Leave\nEmployees are entitled to 15 days of leave.")]
    )

    chunks = chunk_document(doc, "Leave Policy", CONFIG)

    assert len(chunks) == 1
    assert chunks[0].section_path == "1. Annual Leave"


def test_nested_numbering_builds_a_hierarchical_path():
    text = "3. Leave and Time Off\nIntro line.\n3.2 Annual Leave\nFifteen days apply."
    doc = make_document([ExtractedPage(1, text)])

    paths = {c.section_path for c in chunk_document(doc, "Handbook", CONFIG)}

    assert "3. Leave and Time Off / 3.2 Annual Leave" in paths


def test_text_before_any_heading_is_still_chunked():
    doc = make_document([ExtractedPage(1, "A preamble with no heading at all.")])

    chunks = chunk_document(doc, "Handbook", CONFIG)

    assert len(chunks) == 1
    assert chunks[0].section_path is None


def test_no_chunk_exceeds_the_maximum_token_budget():
    long_body = "\n\n".join(sentence("policy", 40) for _ in range(12))
    doc = make_document([ExtractedPage(1, f"1. Long Section\n{long_body}")])

    chunks = chunk_document(doc, "Handbook", CONFIG)

    assert len(chunks) > 1
    assert all(c.token_count <= CONFIG.max_tokens for c in chunks)


def test_consecutive_chunks_in_a_section_overlap():
    long_body = "\n\n".join(sentence(f"clause{i}", 30) for i in range(12))
    doc = make_document([ExtractedPage(1, f"1. Long Section\n{long_body}")])

    chunks = chunk_document(doc, "Handbook", CONFIG)

    # Overlap exists so a fact sitting on a chunk boundary is retrievable from
    # either side of it.
    first_tail_words = set(chunks[0].content.split()[-25:])
    second_words = set(chunks[1].content.split())
    assert first_tail_words & second_words


def test_short_section_stays_as_a_single_chunk():
    doc = make_document([ExtractedPage(1, "1. Brief\nOne short statement.")])

    assert len(chunk_document(doc, "Handbook", CONFIG)) == 1


def test_chunk_indexes_are_sequential_from_zero():
    long_body = "\n\n".join(sentence("term", 40) for _ in range(10))
    doc = make_document([ExtractedPage(1, f"1. Section\n{long_body}")])

    chunks = chunk_document(doc, "Handbook", CONFIG)

    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_pages_are_tracked_across_a_section_that_spans_pages():
    doc = make_document(
        [
            ExtractedPage(1, "1. Leave\n" + sentence("first", 60)),
            ExtractedPage(2, sentence("second", 60)),
        ]
    )

    chunks = chunk_document(doc, "Handbook", CONFIG)

    assert min(c.page_start for c in chunks) == 1
    assert max(c.page_end for c in chunks) == 2
    assert all(c.page_end >= c.page_start for c in chunks)


def test_a_table_that_fits_is_never_split():
    table = ExtractedTable(
        page_number=1,
        header=["Service", "Fee"],
        rows=[["Domestic wire", "15.00"], ["International wire", "35.00"]],
    )
    doc = make_document([ExtractedPage(1, "4. Fees\nThe following fees apply.", [table])])

    chunks = chunk_document(doc, "Products", CONFIG)

    holding = [c for c in chunks if "Domestic wire" in c.content]
    assert len(holding) == 1
    assert "International wire" in holding[0].content


def test_oversized_table_is_split_with_the_header_repeated():
    rows = [[f"Service {i}", f"{i}.00", sentence("note", 12)] for i in range(40)]
    table = ExtractedTable(page_number=1, header=["Service", "Fee", "Notes"], rows=rows)
    doc = make_document([ExtractedPage(1, "4. Fees", [table])])

    chunks = chunk_document(doc, "Products", CONFIG)
    table_chunks = [c for c in chunks if "| Service |" in c.content]

    # Rows are meaningless without their header, so each part must carry it.
    assert len(table_chunks) > 1
    assert all(c.token_count <= CONFIG.max_tokens for c in table_chunks)


def test_every_chunk_has_content_and_a_hash():
    doc = make_document([ExtractedPage(1, "1. Section\nSome content here.")])

    for chunk in chunk_document(doc, "Handbook", CONFIG):
        assert chunk.content.strip()
        assert len(chunk.content_hash) == 64


def test_identical_content_hashes_identically():
    # The embedding cache keys on this, so it must be stable across runs.
    doc = make_document([ExtractedPage(1, "1. Section\nStable content.")])

    first = chunk_document(doc, "Handbook", CONFIG)[0]
    second = chunk_document(doc, "Handbook", CONFIG)[0]

    assert first.content_hash == second.content_hash


def test_empty_document_produces_no_chunks():
    doc = make_document([ExtractedPage(1, "")])

    assert chunk_document(doc, "Handbook", CONFIG) == []
