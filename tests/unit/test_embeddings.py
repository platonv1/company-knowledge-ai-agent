"""Embedding providers.

No test here touches the network. The hashing provider exists so the whole
system is runnable and testable without an API key, and so retrieval tests
exercise real similarity ordering rather than stubbed scores.
"""

import math

import pytest

from app.rag.embeddings import (
    EmbeddingError,
    HashingEmbeddingService,
    OpenAIEmbeddingService,
)

DIMENSIONS = 256


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


@pytest.fixture
def service() -> HashingEmbeddingService:
    return HashingEmbeddingService(dimensions=DIMENSIONS)


async def test_returns_a_vector_of_the_configured_dimension(service):
    vector = await service.embed_query("annual leave entitlement")

    assert len(vector) == DIMENSIONS


async def test_vectors_are_unit_length_so_dot_product_is_cosine(service):
    vector = await service.embed_query("annual leave entitlement")

    assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0, rel_tol=1e-6)


async def test_embeddings_are_deterministic(service):
    first = await service.embed_query("annual leave")
    second = await service.embed_query("annual leave")

    assert first == second


async def test_lexically_related_text_scores_higher_than_unrelated_text(service):
    query = await service.embed_query("how many annual leave days do employees get")
    related = await service.embed_query(
        "Full-time employees are entitled to 15 days of paid annual leave per year."
    )
    unrelated = await service.embed_query(
        "A teller drawer must not hold more than 5,000 in cash at any time."
    )

    assert cosine(query, related) > cosine(query, unrelated)


async def test_embed_documents_preserves_order_and_count(service):
    texts = ["first text", "second text", "third text"]

    vectors = await service.embed_documents(texts)

    assert len(vectors) == 3
    assert vectors[0] == await service.embed_query("first text")


async def test_empty_input_returns_empty_output(service):
    assert await service.embed_documents([]) == []


async def test_blank_text_is_rejected_rather_than_embedded(service):
    # A blank chunk means an upstream bug; embedding it hides the bug.
    with pytest.raises(ValueError):
        await service.embed_query("   ")


class RecordingClient:
    """Stands in for the OpenAI client to assert our batching, not theirs."""

    def __init__(self, dimensions: int):
        self.dimensions = dimensions
        self.batch_sizes: list[int] = []
        self.embeddings = self

    async def create(self, *, input: list[str], model: str, **_):
        self.batch_sizes.append(len(input))

        class Item:
            def __init__(self, vector):
                self.embedding = vector

        class Response:
            def __init__(self, items):
                self.data = items

        return Response([Item([0.0] * self.dimensions) for _ in input])


async def test_openai_provider_splits_large_inputs_into_batches():
    client = RecordingClient(DIMENSIONS)
    service = OpenAIEmbeddingService(
        client=client, model="text-embedding-3-small", dimensions=DIMENSIONS, batch_size=4
    )

    vectors = await service.embed_documents([f"chunk {i}" for i in range(10)])

    assert len(vectors) == 10
    assert client.batch_sizes == [4, 4, 2]


async def test_openai_provider_sends_one_request_for_a_query():
    client = RecordingClient(DIMENSIONS)
    service = OpenAIEmbeddingService(
        client=client, model="text-embedding-3-small", dimensions=DIMENSIONS
    )

    await service.embed_query("what is the vision")

    assert client.batch_sizes == [1]


class FailingClient:
    """Stands in for a provider rejecting the request (bad key, quota, outage)."""

    def __init__(self):
        self.embeddings = self

    async def create(self, **_):
        raise RuntimeError("Error code: 401 - Incorrect API key provided: sk-abc123secret")


async def test_a_provider_failure_is_wrapped_in_embedding_error():
    """An unwrapped provider exception reaches FastAPI as a bare 500 with a
    stack trace, instead of the clean 502 the chat endpoint produces for an LLM
    failure. Callers cannot distinguish "we are broken" from "you sent nonsense"."""
    service = OpenAIEmbeddingService(
        client=FailingClient(), model="text-embedding-3-small", dimensions=DIMENSIONS
    )

    with pytest.raises(EmbeddingError):
        await service.embed_query("a question")


async def test_the_wrapped_error_does_not_echo_the_api_key():
    service = OpenAIEmbeddingService(
        client=FailingClient(), model="text-embedding-3-small", dimensions=DIMENSIONS
    )

    with pytest.raises(EmbeddingError) as exc:
        await service.embed_documents(["some chunk"])

    assert "sk-abc123secret" not in str(exc.value)


async def test_document_embedding_failures_are_wrapped_too():
    service = OpenAIEmbeddingService(
        client=FailingClient(), model="text-embedding-3-small", dimensions=DIMENSIONS
    )

    with pytest.raises(EmbeddingError):
        await service.embed_documents(["chunk one", "chunk two"])


class QuotaExhaustedClient:
    """Reproduces the real failure: a valid key with no credit on the account."""

    def __init__(self):
        self.embeddings = self

    async def create(self, **_):
        raise RuntimeError(
            "Error code: 429 - {'error': {'message': 'You have no credits remaining. "
            "Add credits to continue using the API.', 'type': 'insufficient_quota'}}"
        )


async def test_the_wrapped_error_keeps_the_providers_explanation():
    """Hiding the provider's message turned a one-line diagnosis into a dig.

    "RateLimitError" alone suggests "slow down and retry", when the real cause
    was an exhausted credit balance that retrying never fixes.
    """
    service = OpenAIEmbeddingService(
        client=QuotaExhaustedClient(), model="text-embedding-3-small", dimensions=DIMENSIONS
    )

    with pytest.raises(EmbeddingError) as exc:
        await service.embed_query("a question")

    assert "no credits remaining" in str(exc.value)


async def test_a_key_in_the_providers_message_is_still_redacted():
    # The message is only safe to surface once keys are stripped from it:
    # OpenAI's auth error quotes the key back verbatim.
    service = OpenAIEmbeddingService(
        client=FailingClient(), model="text-embedding-3-small", dimensions=DIMENSIONS
    )

    with pytest.raises(EmbeddingError) as exc:
        await service.embed_query("a question")

    message = str(exc.value)
    assert "sk-abc123secret" not in message
    assert "Incorrect API key provided" in message
    assert "sk-<redacted>" in message
