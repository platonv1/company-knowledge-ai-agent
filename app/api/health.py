"""Health endpoint.

Deliberately does NOT call the LLM or embedding provider. A health check that
makes a paid API call gets hammered by uptime probes and bills you for it; it
reports whether a provider is *configured*, and real reachability is left to
the first genuine request.
"""

from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import func, select

from app.api.deps import AppSettings, DbSession
from app.core.logging import get_logger
from app.models.db import Chunk, Document, IngestStatus

router = APIRouter(tags=["health"])
logger = get_logger(__name__)

PLACEHOLDER_KEYS = {"", "sk-REPLACE-ME", "change-me-in-production"}


@router.get("/health")
async def health(
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    healthy = True

    try:
        chunk_count = await db.scalar(select(func.count()).select_from(Chunk))
        # Only documents that finished ingestion are answerable. The chat page
        # presents this as "answering from N controlled documents", so counting
        # a failed scan here would overstate the knowledge base.
        document_count = await db.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.ingest_status == IngestStatus.READY)
        )
        failed_count = await db.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.ingest_status == IngestStatus.FAILED)
        )
        checks["database"] = {"status": "ok"}
        checks["knowledge_base"] = {
            "chunk_count": chunk_count or 0,
            "document_count": document_count or 0,
            "failed_count": failed_count or 0,
        }
    except Exception as exc:  # noqa: BLE001 - health must report, never raise
        logger.error("Health check could not reach the database: %s", type(exc).__name__)
        healthy = False
        checks["database"] = {"status": "error", "detail": type(exc).__name__}
        checks["knowledge_base"] = {
            "chunk_count": None,
            "document_count": None,
            "failed_count": None,
        }

    checks["llm"] = {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "configured": settings.openai_api_key not in PLACEHOLDER_KEYS,
    }
    checks["embeddings"] = {
        "provider": settings.embedding_provider,
        "model": settings.embedding_model,
        "dimensions": settings.embedding_dimensions,
    }

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if healthy else "error",
        "name": settings.jarvis_name,
        "company": settings.company_name,
        "checks": checks,
    }
