"""FastAPI application factory."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import chat, documents, health
from app.core.config import get_settings
from app.core.database import dispose_engine
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    logger.info("Starting %s for %s", settings.jarvis_name, settings.company_name)
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.jarvis_name} — Company Knowledge Assistant",
        description="Grounded RAG assistant over an approved company knowledge base.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # An unrestricted origin list would turn /api/chat into an open LLM proxy.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Admin-Key"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")

    # Served by the API itself: the chat page has no build step, and the
    # eventual embeddable widget is this same code.
    frontend = Path(__file__).resolve().parent.parent / "frontend" / "chat"
    if frontend.is_dir():
        app.mount("/static", StaticFiles(directory=frontend), name="static")

        @app.get("/", include_in_schema=False)
        async def chat_page() -> FileResponse:
            return FileResponse(frontend / "index.html")

    return app


app = create_app()
