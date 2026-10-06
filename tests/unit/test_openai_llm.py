"""Error handling in the OpenAI LLM provider.

The provider's error text is useful and must survive, but OpenAI's
authentication error quotes the API key back verbatim -- so passing it through
unchanged writes the key into exception messages and logs.
"""

import pytest

from app.llm.base import ChatTurn, LLMError
from app.llm.openai_provider import OpenAILLMService


class FailingClient:
    def __init__(self, message: str):
        self._message = message
        self.chat = self
        self.completions = self

    async def create(self, **_):
        raise RuntimeError(self._message)


def service(message: str) -> OpenAILLMService:
    return OpenAILLMService(client=FailingClient(message), model="gpt-4o")


async def test_a_provider_failure_becomes_an_llm_error():
    with pytest.raises(LLMError):
        await service("boom").complete("sys", [ChatTurn(role="user", content="hi")])


async def test_the_providers_explanation_is_preserved():
    with pytest.raises(LLMError) as exc:
        await service("You have no credits remaining.").complete(
            "sys", [ChatTurn(role="user", content="hi")]
        )

    assert "no credits remaining" in str(exc.value)


async def test_an_api_key_in_the_message_is_redacted():
    with pytest.raises(LLMError) as exc:
        await service("Incorrect API key provided: sk-proj-abc123verysecret").complete(
            "sys", [ChatTurn(role="user", content="hi")]
        )

    message = str(exc.value)
    assert "sk-proj-abc123verysecret" not in message
    assert "sk-<redacted>" in message
