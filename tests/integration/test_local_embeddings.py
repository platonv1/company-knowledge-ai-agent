"""Local embeddings, exercised against the real ONNX model.

Marked integration because it loads a real model (~130MB, cached after first
run). Stubbing it would defeat the purpose: the whole reason this provider
exists is that it understands meaning, and only the real model demonstrates that.
"""

import math

import pytest

from app.rag.embeddings import EmbeddingError, LocalEmbeddingService

MODEL = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384

pytestmark = pytest.mark.integration


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


@pytest.fixture(scope="module")
def service() -> LocalEmbeddingService:
    return LocalEmbeddingService(model_name=MODEL, dimensions=DIMENSIONS)


async def test_returns_vectors_of_the_configured_dimension(service):
    assert len(await service.embed_query("annual leave")) == DIMENSIONS


async def test_vectors_are_unit_length_so_dot_product_is_cosine(service):
    vector = await service.embed_query("annual leave entitlement")

    assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0, rel_tol=1e-5)


async def test_embeddings_are_deterministic(service):
    assert await service.embed_query("annual leave") == await service.embed_query("annual leave")


async def test_it_matches_meaning_rather_than_shared_words(service):
    """The reason this provider exists.

    "time off" and "annual leave" share no words, so a bag-of-words embedder
    scores them near zero. A real model should rank the paraphrase above
    unrelated text by a clear margin.
    """
    query = await service.embed_query("how much time off do staff get")
    paraphrase = await service.embed_query(
        "Full-time employees are entitled to 15 days of paid annual leave."
    )
    unrelated = await service.embed_query(
        "A teller drawer must not hold more than 5,000 in cash at any time."
    )

    assert cosine(query, paraphrase) > cosine(query, unrelated) + 0.1


async def test_it_separates_the_near_miss_distractors(service):
    # The corpus deliberately puts 5,000 / 8,000 / 25,000 cash limits near the
    # 10,000 AML reporting threshold. Retrieval is only meaningful if the model
    # tells these apart.
    query = await service.embed_query(
        "what cash amount must be reported to the financial crime team"
    )
    aml = await service.embed_query(
        "All cash transactions of 10,000 or more must be reported to the Financial Crime team."
    )
    branch = await service.embed_query(
        "A teller drawer must not hold more than 5,000 in cash at any time."
    )

    assert cosine(query, aml) > cosine(query, branch)


async def test_embed_documents_preserves_order_and_count(service):
    vectors = await service.embed_documents(["first text", "second text", "third text"])
    alone = await service.embed_documents(["first text"])

    assert len(vectors) == 3
    assert vectors[0] == alone[0]


async def test_empty_input_returns_empty_output(service):
    assert await service.embed_documents([]) == []


async def test_blank_text_is_rejected(service):
    with pytest.raises(ValueError):
        await service.embed_query("   ")


async def test_a_dimension_mismatch_is_caught_rather_than_stored(service):
    """Configuring the wrong dimension must fail loudly.

    pgvector would reject the insert anyway, but the error there is opaque; and
    a mismatch that slipped through would corrupt the index silently.
    """
    wrong = LocalEmbeddingService(model_name=MODEL, dimensions=1536)

    with pytest.raises(EmbeddingError) as exc:
        await wrong.embed_query("annual leave")

    assert "384" in str(exc.value) and "1536" in str(exc.value)


async def test_the_model_name_is_reported_for_the_index_record(service):
    assert service.model_name == MODEL
