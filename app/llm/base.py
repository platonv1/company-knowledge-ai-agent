"""LLM provider interface (CLAUDE.md s11)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class ChatTurn:
    role: Role
    content: str


class LLMError(Exception):
    pass


class LLMService(ABC):
    @abstractmethod
    async def complete(
        self,
        system: str,
        turns: list[ChatTurn],
        *,
        model: str | None = None,
        max_output_tokens: int = 800,
        temperature: float = 0.0,
    ) -> str:
        """Generate a completion. Temperature defaults to 0: this is a retrieval
        assistant, where reproducibility matters more than variety."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass


@dataclass
class ScriptedLLMService(LLMService):
    """Test double returning queued responses and recording what it was asked.

    Lets tests assert that the LLM is *not* called on a retrieval miss, which is
    the behaviour that makes fabrication structurally impossible there.
    """

    responses: list[str] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)

    @property
    def model_name(self) -> str:
        return "scripted"

    @property
    def call_count(self) -> int:
        return len(self.calls)

    async def complete(
        self,
        system: str,
        turns: list[ChatTurn],
        *,
        model: str | None = None,
        max_output_tokens: int = 800,
        temperature: float = 0.0,
    ) -> str:
        self.calls.append(
            {"system": system, "turns": list(turns), "model": model, "temperature": temperature}
        )
        if not self.responses:
            raise LLMError("ScriptedLLMService ran out of queued responses.")
        return self.responses.pop(0)
