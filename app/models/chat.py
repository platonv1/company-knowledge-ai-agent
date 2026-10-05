"""Chat API schemas."""

import uuid

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: uuid.UUID | None = None


class SourceOut(BaseModel):
    marker: str
    document: str
    document_title: str
    page: int
    page_label: str
    section: str | None = None
    version: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceOut]
    conversation_id: uuid.UUID
    # False when the answer is a refusal, so the UI can render it as a distinct
    # state rather than as an answer.
    grounded: bool
    retrieved_count: int = 0
    rewritten_query: str | None = None
