"""Logging setup.

Never log API keys, full document bodies, or user PII (CLAUDE.md s27). Queries
are logged truncated for this reason.
"""

import logging
import re
import sys

from app.core.config import get_settings

MAX_LOGGED_TEXT = 120

# Provider errors quote the API key back ("Incorrect API key provided: sk-..."),
# so any key is stripped before a message is surfaced or logged.
_API_KEY = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-5s [%(name)s] %(message)s", "%H:%M:%S")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
    # asyncpg/sqlalchemy are noisy at INFO and can echo parameter values.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def redact_keys(text: str) -> str:
    """Remove anything shaped like an API key from free text."""
    return _API_KEY.sub("sk-<redacted>", text)


def truncate(text: str, limit: int = MAX_LOGGED_TEXT) -> str:
    """Shorten free text before logging it."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit] + "..."


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
