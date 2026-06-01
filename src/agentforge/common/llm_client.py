from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LLMProviderError(RuntimeError):
    """Raised when a configured model provider cannot complete a request."""


class LLMClient(Protocol):
    """Minimal interface for model-backed generation."""

    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        """Return model output for a prompt."""

    def metadata(self) -> dict[str, object]:
        """Return non-secret provider metadata for traces."""


@dataclass
class NotConfiguredLLMClient:
    """Placeholder adapter used until a provider is configured."""

    reason: str = "No LLM provider configured. Phase 1 uses deterministic local generation."

    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        raise RuntimeError(self.reason)

    def metadata(self) -> dict[str, object]:
        return {"provider": "not_configured", "configured": False}
