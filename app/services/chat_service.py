"""Chat orchestration.

The pipeline, in order:

1. Rewrite a follow-up into a standalone question (skipped on the first turn,
   which saves a round trip on most requests).
2. Retrieve and gate.
3. If nothing cleared the gate, return the refusal **without calling the LLM**.
   This is the one place where a hallucination would be most damaging, so it is
   prevented structurally rather than by instruction.
4. Build the delimited context, generate, resolve markers into citations.
5. Persist both turns, recording which chunks the answer cited.
"""

import uuid
from dataclasses import dataclass, field

from app.core.logging import get_logger, truncate
from app.llm.base import ChatTurn, LLMService
from app.llm.prompts import (
    CONTEXTUALISER_SYSTEM_PROMPT,
    REFUSAL_MARKER,
    REFUSAL_TEXT,
    answer_prompt,
    contextualiser_prompt,
    system_prompt,
)
from app.models.db import Role
from app.rag.citations import Citation, resolve_citations
from app.rag.context_builder import build_context
from app.rag.retriever import Retriever
from app.repositories.conversation_repository import ConversationRepository

logger = get_logger(__name__)

MAX_QUESTION_CHARS = 2000
MAX_REWRITE_TOKENS = 120


@dataclass(frozen=True)
class ChatAnswer:
    answer: str
    conversation_id: uuid.UUID
    grounded: bool
    sources: list[Citation] = field(default_factory=list)
    retrieved_count: int = 0
    rewritten_query: str | None = None
    best_score: float | None = None
    # The passages the answer was built from. Not returned over HTTP; used by
    # the evaluation judge, which must see the evidence to assess whether the
    # answer is supported by it, and by anyone debugging a bad answer.
    context_text: str | None = None


class ChatService:
    def __init__(
        self,
        retriever: Retriever,
        llm: LLMService,
        conversations: ConversationRepository,
        *,
        assistant_name: str,
        company_name: str,
        history_window: int = 6,
        fast_model: str | None = None,
    ):
        self._retriever = retriever
        self._llm = llm
        self._conversations = conversations
        self._system_prompt = system_prompt(assistant_name, company_name)
        self._history_window = history_window
        self._fast_model = fast_model

    async def answer(
        self,
        message: str,
        *,
        org_id: uuid.UUID,
        conversation_id: uuid.UUID | None = None,
    ) -> ChatAnswer:
        question = (message or "").strip()
        if not question:
            raise ValueError("Message cannot be empty.")
        if len(question) > MAX_QUESTION_CHARS:
            raise ValueError(f"Message exceeds {MAX_QUESTION_CHARS} characters.")

        conversation = await self._conversations.get_or_create(org_id, conversation_id)
        history = await self._conversations.recent_turns(conversation.id, self._history_window)

        search_query, rewritten = await self._resolve_query(question, history)

        retrieval = await self._retriever.retrieve(search_query, org_id)

        if not retrieval.grounded:
            return await self._refuse(conversation.id, question, retrieval, rewritten)

        context = build_context(retrieval.chunks)
        raw_answer = await self._llm.complete(
            self._system_prompt,
            [ChatTurn(role="user", content=answer_prompt(context.text, question))],
        )
        resolved = resolve_citations(raw_answer, context.source_map)

        # A refusal from the model means the retrieved chunks did not actually
        # answer the question, even though they cleared the relevance gate.
        grounded = REFUSAL_MARKER not in resolved.answer and bool(resolved.citations)

        await self._conversations.append(conversation.id, Role.USER, question)
        await self._conversations.append(
            conversation.id,
            Role.ASSISTANT,
            resolved.answer,
            cited_chunk_ids=[c.chunk_id for c in resolved.citations] or None,
        )

        logger.info(
            "Answered %r: grounded=%s, %d sources, best score %.3f",
            truncate(question, 60),
            grounded,
            len(resolved.citations),
            retrieval.best_score or 0.0,
        )

        return ChatAnswer(
            answer=resolved.answer,
            conversation_id=conversation.id,
            grounded=grounded,
            sources=resolved.citations,
            retrieved_count=len(retrieval.chunks),
            rewritten_query=rewritten,
            best_score=retrieval.best_score,
            context_text=context.text,
        )

    async def _resolve_query(
        self, question: str, history: list[ChatTurn]
    ) -> tuple[str, str | None]:
        """Rewrite a follow-up into a standalone question."""
        if not history:
            # No history means nothing to resolve against, so skip the call.
            return question, None

        rewritten = await self._llm.complete(
            CONTEXTUALISER_SYSTEM_PROMPT,
            [ChatTurn(role="user", content=contextualiser_prompt(history, question))],
            model=self._fast_model,
            max_output_tokens=MAX_REWRITE_TOKENS,
        )
        rewritten = rewritten.strip().strip('"')

        if not rewritten:
            return question, None

        logger.info("Rewrote %r to %r", truncate(question, 40), truncate(rewritten, 60))
        return rewritten, rewritten

    async def _refuse(
        self,
        conversation_id: uuid.UUID,
        question: str,
        retrieval,
        rewritten: str | None,
    ) -> ChatAnswer:
        logger.info(
            "Refusing %r: nothing cleared the relevance gate (%d candidates rejected)",
            truncate(question, 60),
            len(retrieval.rejected),
        )
        await self._conversations.append(conversation_id, Role.USER, question)
        await self._conversations.append(conversation_id, Role.ASSISTANT, REFUSAL_TEXT)

        return ChatAnswer(
            answer=REFUSAL_TEXT,
            conversation_id=conversation_id,
            grounded=False,
            sources=[],
            retrieved_count=0,
            rewritten_query=rewritten,
            best_score=None,
        )
