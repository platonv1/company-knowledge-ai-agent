"""Authentication for administrative endpoints.

A single shared admin key is the right weight for Phase 1: document management
is an operator task, not an end-user one. Comparison is constant time so the
endpoint does not leak the key through response timing.
"""

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

PLACEHOLDER_ADMIN_KEYS = {"", "change-me-in-production"}


async def require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    """Reject a request without a valid admin key."""
    settings = get_settings()

    if settings.admin_api_key in PLACEHOLDER_ADMIN_KEYS:
        # Failing closed matters more than convenience: a placeholder key in
        # production would leave document management wide open.
        logger.error("ADMIN_API_KEY is unset or still the placeholder value.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrative access is not configured.",
        )

    if not x_admin_key or not secrets.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid X-Admin-Key header is required.",
        )
