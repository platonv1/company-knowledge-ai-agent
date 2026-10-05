"""Application settings.

Every retrieval-tuning knob lives here rather than inline, because Milestone 8
calibrates them against the golden set and they must be changeable without a
code edit.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Application ----
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # ---- Branding ----
    jarvis_name: str = "Jarvis"
    company_name: str = "Jarvis Financial Group"
    # Single organization in Phase 1, but the slug is a real lookup key so
    # multi-tenancy is a routing change rather than a schema change.
    org_slug: str = "jarvis-financial-group"

    # ---- Database ----
    database_url: str

    # ---- Providers ----
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    # Used only for query contextualisation, which runs on every follow-up turn.
    llm_fast_model: str = "gpt-4o-mini"

    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=1536, gt=0)

    openai_api_key: str

    # ---- Retrieval tuning (calibrated in Milestone 8) ----
    search_k: int = Field(default=8, ge=1, le=100)
    top_k: int = Field(default=5, ge=1, le=50)
    relevance_floor: float = Field(default=0.35, ge=0.0, le=1.0)
    relative_dropoff: float = Field(default=0.75, ge=0.0, le=1.0)

    # ---- Chunking ----
    chunk_target_tokens: int = Field(default=600, ge=50)
    chunk_max_tokens: int = Field(default=800, ge=50)
    chunk_overlap_ratio: float = Field(default=0.12, ge=0.0, lt=0.5)

    # ---- Conversation ----
    history_window_messages: int = Field(default=6, ge=0, le=50)

    # ---- Security ----
    admin_api_key: str
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:8000"]
    )
    chat_rate_limit_per_minute: int = Field(default=20, ge=1)

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string so the value stays readable in .env."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _check_retrieval_coherence(self) -> "Settings":
        if self.top_k > self.search_k:
            raise ValueError(
                f"TOP_K ({self.top_k}) cannot exceed SEARCH_K ({self.search_k}): "
                "we cannot keep more chunks than we retrieve."
            )
        if self.chunk_target_tokens > self.chunk_max_tokens:
            raise ValueError(
                f"CHUNK_TARGET_TOKENS ({self.chunk_target_tokens}) cannot exceed "
                f"CHUNK_MAX_TOKENS ({self.chunk_max_tokens})."
            )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def chunk_overlap_tokens(self) -> int:
        return int(self.chunk_target_tokens * self.chunk_overlap_ratio)


@lru_cache
def get_settings() -> Settings:
    """Cached so the FastAPI dependency does not re-read the environment per request."""
    return Settings()  # type: ignore[call-arg]
