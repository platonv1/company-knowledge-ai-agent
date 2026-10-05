"""Chat endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import AppSettings, ChatServiceDep, OrgId, client_key, get_rate_limiter
from app.core.logging import get_logger
from app.core.rate_limit import TokenBucketLimiter
from app.llm.base import LLMError
from app.models.chat import ChatRequest, ChatResponse, SourceOut
from app.repositories.conversation_repository import ConversationNotFoundError

router = APIRouter(tags=["chat"])
logger = get_logger(__name__)


def enforce_rate_limit(
    request: Request,
    response: Response,
    limiter: Annotated[TokenBucketLimiter, Depends(get_rate_limiter)],
) -> None:
    key = client_key(request)
    if limiter.allow(key):
        return

    retry_after = max(1, int(limiter.retry_after(key)) + 1)
    response.headers["Retry-After"] = str(retry_after)
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests. Please wait a moment and try again.",
        headers={"Retry-After": str(retry_after)},
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def chat(
    payload: ChatRequest,
    service: ChatServiceDep,
    org_id: OrgId,
    settings: AppSettings,
) -> ChatResponse:
    try:
        result = await service.answer(
            payload.message, org_id=org_id, conversation_id=payload.conversation_id
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except LLMError as exc:
        # The provider failing is not the caller's fault, and the detail must not
        # leak keys or request internals.
        logger.error("LLM request failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{settings.jarvis_name} could not reach the language model. Please retry.",
        ) from exc

    return ChatResponse(
        answer=result.answer,
        conversation_id=result.conversation_id,
        grounded=result.grounded,
        retrieved_count=result.retrieved_count,
        rewritten_query=result.rewritten_query,
        sources=[
            SourceOut(
                marker=source.marker,
                document=source.document,
                document_title=source.document_title,
                page=source.page,
                page_label=source.page_label,
                section=source.section,
                version=source.version,
            )
            for source in result.sources
        ],
    )
