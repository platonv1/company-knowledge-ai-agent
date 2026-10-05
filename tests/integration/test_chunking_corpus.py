"""Chunking measured against the golden set.

This is the real gate for the chunking milestone: unit tests prove the rules
behave, but only this proves the rules preserve the facts. If an answer is
severed from its section or attributed to the wrong page here, retrieval cannot
recover later no matter how good the embeddings are.
"""

import re

import pytest

from app.rag.chunking import ChunkConfig, chunk_document, embedding_text
from app.rag.extraction import extract_document
from scripts.corpus_content import SCANNED_DOCUMENT_FILENAME
from scripts.generate_corpus import generate_corpus

CONFIG = ChunkConfig(target_tokens=600, max_tokens=800, overlap_ratio=0.12)


def comparable(text: str) -> str:
    """Normalise for substring comparison, ignoring table pipes and whitespace."""
    return re.sub(r"\s+", " ", text.replace("|", " ")).strip()


@pytest.fixture(scope="module")
def chunked_corpus(tmp_path_factory):
    out = tmp_path_factory.mktemp("chunk_corpus")
    result = generate_corpus(out, facts_path=out / "facts.yaml")

    chunks_by_document = {}
    for doc in result.documents:
        if doc.filename == SCANNED_DOCUMENT_FILENAME:
            continue
        extracted = extract_document(doc.path)
        chunks_by_document[doc.filename] = chunk_document(extracted, doc.title, CONFIG)

    return result, chunks_by_document


def test_every_document_produces_chunks(chunked_corpus):
    _, chunks_by_document = chunked_corpus

    empty = [name for name, chunks in chunks_by_document.items() if not chunks]
    assert empty == []


def test_every_golden_fact_survives_chunking(chunked_corpus):
    result, chunks_by_document = chunked_corpus

    missing = []
    for fact in result.facts:
        anchor = comparable(fact.anchor)
        if not any(anchor in comparable(c.content) for c in chunks_by_document[fact.document]):
            missing.append(fact.id)

    assert missing == [], f"facts severed by chunking: {missing}"


def test_page_attribution_is_correct_for_every_fact(chunked_corpus):
    # A correct answer with a wrong page number is still a citation failure.
    result, chunks_by_document = chunked_corpus

    wrong = []
    for fact in result.facts:
        anchor = comparable(fact.anchor)
        holders = [c for c in chunks_by_document[fact.document] if anchor in comparable(c.content)]
        if not any(c.page_start <= fact.page <= c.page_end for c in holders):
            wrong.append((fact.id, fact.page, [(c.page_start, c.page_end) for c in holders]))

    assert wrong == [], f"page attribution wrong: {wrong}"


def test_no_chunk_exceeds_the_token_budget(chunked_corpus):
    _, chunks_by_document = chunked_corpus

    oversized = [
        (name, c.chunk_index, c.token_count)
        for name, chunks in chunks_by_document.items()
        for c in chunks
        if c.token_count > CONFIG.max_tokens
    ]
    assert oversized == []


def test_most_chunks_carry_a_section_path(chunked_corpus):
    # Section context is what makes a citation readable and improves the
    # embedding. Title-page text legitimately has none, so this is a ratio.
    _, chunks_by_document = chunked_corpus

    all_chunks = [c for chunks in chunks_by_document.values() for c in chunks]
    with_section = [c for c in all_chunks if c.section_path]

    assert len(with_section) / len(all_chunks) > 0.8


def test_embedding_text_carries_document_and_section_context(chunked_corpus):
    _, chunks_by_document = chunked_corpus

    chunk = next(c for c in chunks_by_document["Leave_Policy_v2.pdf"] if c.section_path)
    text = embedding_text(chunk, "Annual Leave Policy")

    assert text.startswith("Annual Leave Policy — ")
    assert chunk.content in text


def test_the_two_leave_policies_produce_distinguishable_chunks(chunked_corpus):
    _, chunks_by_document = chunked_corpus

    v2 = " ".join(c.content for c in chunks_by_document["Leave_Policy_v2.pdf"])
    v1 = " ".join(c.content for c in chunks_by_document["Leave_Policy_v1.pdf"])

    assert "15 days of paid annual leave" in v2
    assert "12 days of paid annual leave" in v1


def test_corpus_chunk_count_is_reported(chunked_corpus):
    # Not an assertion about quality -- a visible number, so a change in chunking
    # strategy shows up as a diff rather than passing silently.
    _, chunks_by_document = chunked_corpus

    total = sum(len(c) for c in chunks_by_document.values())
    print(f"\ncorpus chunks: {total}")
    for name in sorted(chunks_by_document):
        print(f"  {name:<40} {len(chunks_by_document[name]):>3}")

    assert total > 30
