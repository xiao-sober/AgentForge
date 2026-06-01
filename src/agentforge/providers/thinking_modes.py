from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ThinkingModeConfigError(ValueError):
    """Raised when thinking mode configuration is invalid."""


@dataclass(frozen=True)
class ThinkingModeConfig:
    enabled: bool = False
    provider: str = "auto"
    thinking_budget: int | None = None
    preserve_thinking: bool | None = None

    def metadata(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "enabled": self.enabled,
            "provider": self.provider,
        }
        if self.thinking_budget is not None:
            payload["thinking_budget"] = self.thinking_budget
        if self.preserve_thinking is not None:
            payload["preserve_thinking"] = self.preserve_thinking
        return payload


def parse_thinking_mode_config(raw: Any, provider_name: str) -> ThinkingModeConfig:
    if raw is None:
        return ThinkingModeConfig()
    if isinstance(raw, bool):
        return ThinkingModeConfig(enabled=raw)
    if not isinstance(raw, dict):
        raise ThinkingModeConfigError(
            f"Provider '{provider_name}' field 'thinking_mode' must be a boolean or an object."
        )

    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ThinkingModeConfigError(
            f"Provider '{provider_name}' field 'thinking_mode.enabled' must be a boolean."
        )

    provider = raw.get("provider", "auto")
    if not isinstance(provider, str) or not provider.strip():
        raise ThinkingModeConfigError(
            f"Provider '{provider_name}' field 'thinking_mode.provider' must be a non-empty string."
        )

    thinking_budget = raw.get("thinking_budget")
    if thinking_budget is not None:
        if not isinstance(thinking_budget, int) or thinking_budget <= 0:
            raise ThinkingModeConfigError(
                f"Provider '{provider_name}' field 'thinking_mode.thinking_budget' must be a positive integer."
            )

    preserve_thinking = raw.get("preserve_thinking")
    if preserve_thinking is not None and not isinstance(preserve_thinking, bool):
        raise ThinkingModeConfigError(
            f"Provider '{provider_name}' field 'thinking_mode.preserve_thinking' must be a boolean."
        )

    return ThinkingModeConfig(
        enabled=enabled,
        provider=provider.strip(),
        thinking_budget=thinking_budget,
        preserve_thinking=preserve_thinking,
    )


def apply_thinking_mode(
    body: dict[str, Any],
    thinking_mode: ThinkingModeConfig,
    model: str,
) -> dict[str, Any]:
    if not thinking_mode.enabled:
        return body

    provider = _resolve_provider(thinking_mode.provider, model)
    if provider == "qwen":
        return _apply_qwen_thinking_mode(body, thinking_mode)
    raise ThinkingModeConfigError(f"Unsupported thinking mode provider '{thinking_mode.provider}'.")


def _resolve_provider(provider: str, model: str) -> str:
    normalized = provider.lower().strip()
    if normalized != "auto":
        return normalized
    if model.lower().startswith("qwen"):
        return "qwen"
    raise ThinkingModeConfigError(
        "thinking_mode.provider is 'auto', but the model family could not be inferred. "
        "Set thinking_mode.provider explicitly."
    )


def _apply_qwen_thinking_mode(body: dict[str, Any], thinking_mode: ThinkingModeConfig) -> dict[str, Any]:
    body["enable_thinking"] = True
    if thinking_mode.thinking_budget is not None:
        body["thinking_budget"] = thinking_mode.thinking_budget
    if thinking_mode.preserve_thinking is not None:
        body["preserve_thinking"] = thinking_mode.preserve_thinking
    return body
