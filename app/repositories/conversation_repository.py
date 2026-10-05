"""Conversation persistence.

History is stored so a follow-up can be resolved against it, and so the chunks
an answer cited are auditable after the fact.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import ChatTurn
from app.models.db import Conversation, Message, Role


class ConversationNotFoundError(Exception):
    """The caller supplied a conversation_id that does not exist."""


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, org_id: uuid.UUID) -> Conversation:
        conversation = Conversation(org_id=org_id)
        self._session.add(conversation)
        await self._session.commit()
        return conversation

    async def get(self, conversation_id: uuid.UUID) -> Conversation:
        conversation = await self._session.get(Conversation, conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(f"No conversation with id {conversation_id}.")
        return conversation

    async def get_or_create(
        self, org_id: uuid.UUID, conversation_id: uuid.UUID | None
    ) -> Conversation:
        if conversation_id is None:
            return await self.create(org_id)
        return await self.get(conversation_id)

    async def append(
        self,
        conversation_id: uuid.UUID,
        role: Role,
        content: str,
        cited_chunk_ids: list[uuid.UUID] | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            cited_chunk_ids=cited_chunk_ids,
        )
        self._session.add(message)
        await self._session.commit()
        return message

    async def messages(self, conversation_id: uuid.UUID) -> list[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at, Message.id)
        )
        return list(result.scalars())

    async def recent_turns(self, conversation_id: uuid.UUID, limit: int) -> list[ChatTurn]:
        """The last `limit` messages, oldest first.

        Used only to resolve references in a follow-up question. It is never
        passed to the answering model as evidence, so stale conversation content
        cannot override the knowledge base (CLAUDE.md s17).
        """
        if limit <= 0:
            return []

        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        messages = list(result.scalars())[::-1]
        return [ChatTurn(role=m.role.value, content=m.content) for m in messages]
