"""OpenAI implementation of LLMService."""

from app.core.logging import get_logger, redact_keys
from app.llm.base import ChatTurn, LLMError, LLMService

logger = get_logger(__name__)


class OpenAILLMService(LLMService):
    def __init__(self, client, model: str, fast_model: str | None = None):
        self._client = client
        self._model = model
        self._fast_model = fast_model or model

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def fast_model_name(self) -> str:
        return self._fast_model

    async def complete(
        self,
        system: str,
        turns: list[ChatTurn],
        *,
        model: str | None = None,
        max_output_tokens: int = 800,
        temperature: float = 0.0,
    ) -> str:
        messages = [{"role": "system", "content": system}]
        messages += [{"role": turn.role, "content": turn.content} for turn in turns]

        try:
            response = await self._client.chat.completions.create(
                model=model or self._model,
                messages=messages,
                max_completion_tokens=max_output_tokens,
                temperature=temperature,
            )
        except Exception as exc:  # noqa: BLE001 - wrapped so callers see one error type
            # The provider's message is kept because it explains the failure,
            # but OpenAI's auth error quotes the API key back, so it is
            # redacted before it can reach an exception message or a log line.
            raise LLMError(f"LLM request failed: {redact_keys(str(exc))}") from exc

        content = response.choices[0].message.content
        if not content or not content.strip():
            raise LLMError("LLM returned an empty completion.")
        return content.strip()


def build_llm_service(settings) -> LLMService:
    provider = settings.llm_provider.lower()

    if provider == "openai":
        from openai import AsyncOpenAI

        return OpenAILLMService(
            client=AsyncOpenAI(api_key=settings.openai_api_key),
            model=settings.llm_model,
            fast_model=settings.llm_fast_model,
        )

    if provider == "extractive":
        # Offline sentence selection. Runs with no API key; see app/llm/extractive.py.
        from app.llm.extractive import ExtractiveLLMService

        return ExtractiveLLMService()

    raise LLMError(
        f"Unknown LLM_PROVIDER {settings.llm_provider!r}; expected 'openai' or 'extractive'."
    )
