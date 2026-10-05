"""Shared FastAPI dependencies.

Declared as `Annotated` aliases rather than `= Depends(...)` defaults, which
keeps signatures short and avoids the mutable-default pattern linters flag.

The service providers are dependencies rather than module globals so tests can
override them -- which is how the chat tests inject a scripted LLM instead of
calling a real provider.
"""

import uuid
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.rate_limit import TokenBucketLimiter
from app.llm.base import LLMService
from app.llm.openai_provider import build_llm_service
from app.rag.chunking import ChunkConfig
from app.rag.embeddings import EmbeddingService, build_embedding_service
from app.rag.retriever import RetrievalConfig, Retriever
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.vector_store import PgVectorStore
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService, get_or_create_organization

DbSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


# Provider clients are cached: building an HTTP client per request is wasteful,
# and the embedding model must stay identical across requests or stored and
# query vectors stop being comparable.
@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return build_embedding_service(get_settings())


@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    return build_llm_service(get_settings())


@lru_cache(maxsize=1)
def get_rate_limiter() -> TokenBucketLimiter:
    return TokenBucketLimiter(per_minute=get_settings().chat_rate_limit_per_minute)


async def get_org_id(db: DbSession, settings: AppSettings) -> uuid.UUID:
    """Resolve the organization this request belongs to.

    Phase 1 serves one organization, resolved by slug. Multi-tenancy becomes a
    change here -- reading a tenant from the host or an API key -- rather than a
    change to every query, because org_id is already threaded through the data
    model.
    """
    organization = await get_or_create_organization(
        db, name=settings.company_name, slug=settings.org_slug
    )
    return organization.id


OrgId = Annotated[uuid.UUID, Depends(get_org_id)]


def get_chat_service(
    db: DbSession,
    settings: AppSettings,
    llm: Annotated[LLMService, Depends(get_llm_service)],
    embedder: Annotated[EmbeddingService, Depends(get_embedding_service)],
) -> ChatService:
    retriever = Retriever(
        store=PgVectorStore(db),
        embedder=embedder,
        config=RetrievalConfig.from_settings(settings),
    )
    return ChatService(
        retriever=retriever,
        llm=llm,
        conversations=ConversationRepository(db),
        assistant_name=settings.jarvis_name,
        company_name=settings.company_name,
        history_window=settings.history_window_messages,
        fast_model=settings.llm_fast_model,
    )


def get_document_service(
    db: DbSession,
    settings: AppSettings,
    embedder: Annotated[EmbeddingService, Depends(get_embedding_service)],
) -> DocumentService:
    return DocumentService(
        session=db,
        store=PgVectorStore(db),
        embedder=embedder,
        chunk_config=ChunkConfig(
            target_tokens=settings.chunk_target_tokens,
            max_tokens=settings.chunk_max_tokens,
            overlap_ratio=settings.chunk_overlap_ratio,
        ),
    )


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]


def client_key(request: Request) -> str:
    """Identify the caller for rate limiting.

    X-Forwarded-For is trusted only because this sits behind a proxy we control;
    exposed directly, a client could spoof it to evade the limit.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
