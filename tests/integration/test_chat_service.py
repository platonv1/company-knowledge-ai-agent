"""Chat orchestration, with a scripted LLM and a real database.

The LLM is scripted so the tests assert our behaviour rather than a model's.
The most important assertions are negative: on a retrieval miss the LLM must
not be called at all, and an invented citation must not reach the caller.
"""

import uuid

import pytest

from app.llm.base import ScriptedLLMService
from app.llm.prompts import REFUSAL_MARKER, REFUSAL_TEXT
from app.rag.retriever import RetrievalConfig, Retriever
from app.repositories.conversation_repository import (
    ConversationNotFoundError,
    ConversationRepository,
)
from app.repositories.vector_store import SearchFilters, SearchResult, VectorStore
from app.services.chat_service import ChatService
from app.services.document_service import get_or_create_organization

pytestmark = pytest.mark.integration


def search_result(
    content: str = "Full-time employees are entitled to 15 days of paid annual leave.",
    *,
    score: float = 0.82,
    filename: str = "Leave_Policy_v2.pdf",
    page: int = 2,
) -> SearchResult:
    return SearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_filename=filename,
        document_title="Annual Leave Policy",
        document_version="2.0",
        doc_type="HR Policy",
        effective_date=None,
        page_start=page,
        page_end=page,
        section_path="2. Annual Leave Entitlement",
        content=content,
        score=score,
    )


class StubStore(VectorStore):
    def __init__(self, results: list[SearchResult]):
        self.results = results
        self.queries: list[list[float]] = []

    async def search(self, query_embedding, filters: SearchFilters, limit: int):
        self.queries.append(query_embedding)
        return self.results[:limit]

    async def add_chunks(self, **_):
        raise NotImplementedError

    async def delete_document(self, document_id):
        raise NotImplementedError

    async def set_document_status(self, document_id, status):
        raise NotImplementedError

    async def count_chunks(self, org_id):
        return len(self.results)


class RecordingEmbedder:
    dimensions = 8
    model_name = "recording"

    def __init__(self):
        self.embedded: list[str] = []

    async def embed_query(self, text: str):
        self.embedded.append(text)
        return [0.1] * self.dimensions

    async def embed_documents(self, texts):
        return [[0.1] * self.dimensions for _ in texts]


@pytest.fixture
async def org(db_session):
    return await get_or_create_organization(db_session, name="Jarvis Financial Group", slug="jfg")


def build_service(db_session, results, responses):
    embedder = RecordingEmbedder()
    retriever = Retriever(
        store=StubStore(results),
        embedder=embedder,
        config=RetrievalConfig(search_k=8, top_k=5, relevance_floor=0.35, relative_dropoff=0.75),
    )
    llm = ScriptedLLMService(responses=list(responses))
    service = ChatService(
        retriever=retriever,
        llm=llm,
        conversations=ConversationRepository(db_session),
        assistant_name="Jarvis",
        company_name="Jarvis Financial Group",
        history_window=6,
    )
    return service, llm, embedder


async def test_a_grounded_question_is_answered_with_resolved_sources(db_session, org):
    service, _, _ = build_service(
        db_session,
        [search_result()],
        ["Full-time employees receive 15 days of paid annual leave. [S1]"],
    )

    answer = await service.answer("How many annual leave days do employees get?", org_id=org.id)

    assert answer.grounded is True
    assert "15 days" in answer.answer
    assert len(answer.sources) == 1
    assert answer.sources[0].document == "Leave_Policy_v2.pdf"
    assert answer.sources[0].page == 2


async def test_a_retrieval_miss_refuses_without_calling_the_llm(db_session, org):
    # Structural guarantee: with no evidence there is no model call, so there is
    # nothing that could fabricate an answer.
    service, llm, _ = build_service(db_session, [search_result(score=0.10)], [])

    answer = await service.answer("Does the company offer pet insurance?", org_id=org.id)

    assert answer.grounded is False
    assert answer.answer == REFUSAL_TEXT
    assert answer.sources == []
    assert llm.call_count == 0


async def test_an_invented_citation_is_stripped_and_not_returned(db_session, org):
    service, _, _ = build_service(
        db_session,
        [search_result()],
        ["Employees receive 15 days. [S1] The CEO approved this. [S7]"],
    )

    answer = await service.answer("How many leave days?", org_id=org.id)

    assert "[S7]" not in answer.answer
    assert [s.marker for s in answer.sources] == ["S1"]


async def test_a_model_refusal_is_reported_as_not_grounded(db_session, org):
    # Chunks cleared the gate but did not actually answer the question. The flag
    # must reflect the answer, not just whether retrieval returned something.
    service, _, _ = build_service(db_session, [search_result()], [REFUSAL_TEXT])

    answer = await service.answer("What is the dividend policy?", org_id=org.id)

    assert answer.grounded is False
    assert REFUSAL_MARKER in answer.answer


async def test_the_first_turn_does_not_pay_for_query_rewriting(db_session, org):
    service, llm, embedder = build_service(
        db_session, [search_result()], ["Employees get 15 days. [S1]"]
    )

    await service.answer("What is the annual leave policy?", org_id=org.id)

    assert llm.call_count == 1
    assert embedder.embedded == ["What is the annual leave policy?"]


async def test_a_follow_up_is_rewritten_before_retrieval(db_session, org):
    # "How many days?" retrieves noise unless it is rewritten against the
    # previous turn. This is the behaviour CLAUDE.md s17 implies but s13 omits.
    service, llm, embedder = build_service(
        db_session,
        [search_result()],
        [
            "The company provides several categories of leave. [S1]",
            "How many annual leave days do employees get?",
            "Employees receive 15 days of annual leave. [S1]",
        ],
    )

    first = await service.answer("What is the annual leave policy?", org_id=org.id)
    second = await service.answer(
        "How many days?", org_id=org.id, conversation_id=first.conversation_id
    )

    assert llm.call_count == 3  # answer, rewrite, answer
    assert second.rewritten_query == "How many annual leave days do employees get?"
    assert embedder.embedded[-1] == "How many annual leave days do employees get?"


async def test_conversation_history_is_persisted_with_roles(db_session, org):
    service, _, _ = build_service(db_session, [search_result()], ["Employees get 15 days. [S1]"])

    answer = await service.answer("How many leave days?", org_id=org.id)

    turns = await ConversationRepository(db_session).recent_turns(answer.conversation_id, limit=10)
    assert [t.role for t in turns] == ["user", "assistant"]
    assert turns[0].content == "How many leave days?"


async def test_cited_chunk_ids_are_recorded_for_audit(db_session, org):
    chunk = search_result()
    service, _, _ = build_service(db_session, [chunk], ["Employees get 15 days. [S1]"])

    answer = await service.answer("How many leave days?", org_id=org.id)

    messages = await ConversationRepository(db_session).messages(answer.conversation_id)
    assistant_message = messages[-1]
    assert assistant_message.cited_chunk_ids == [chunk.chunk_id]


async def test_reusing_a_conversation_id_continues_the_same_thread(db_session, org):
    service, _, _ = build_service(
        db_session,
        [search_result()],
        ["First answer. [S1]", "How many days of annual leave?", "Second answer. [S1]"],
    )

    first = await service.answer("What is the leave policy?", org_id=org.id)
    second = await service.answer(
        "How many days?", org_id=org.id, conversation_id=first.conversation_id
    )

    assert second.conversation_id == first.conversation_id
    turns = await ConversationRepository(db_session).recent_turns(first.conversation_id, limit=10)
    assert len(turns) == 4


async def test_an_unknown_conversation_id_is_an_error(db_session, org):
    service, _, _ = build_service(db_session, [search_result()], ["x"])

    with pytest.raises(ConversationNotFoundError):
        await service.answer("question", org_id=org.id, conversation_id=uuid.uuid4())


async def test_an_empty_message_is_rejected(db_session, org):
    service, _, _ = build_service(db_session, [search_result()], ["x"])

    with pytest.raises(ValueError):
        await service.answer("   ", org_id=org.id)


async def test_the_answer_carries_the_context_it_was_built_from(db_session, org):
    """The evaluation judge has to see the passages the answer was based on.

    Re-retrieving them afterwards is not equivalent: a follow-up is answered
    against a rewritten query, so a second retrieval can return a different set.
    """
    service, _, _ = build_service(
        db_session, [search_result()], ["Employees receive 15 days. [S1]"]
    )

    answer = await service.answer("How many leave days?", org_id=org.id)

    assert "15 days of paid annual leave" in answer.context_text
    assert '<source id="S1"' in answer.context_text


async def test_a_refusal_carries_no_context(db_session, org):
    service, _, _ = build_service(db_session, [search_result(score=0.1)], [])

    answer = await service.answer("Does the company offer pet insurance?", org_id=org.id)

    assert answer.context_text is None
