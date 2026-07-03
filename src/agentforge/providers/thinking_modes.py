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
    reasoning_effort: str | None = None
    configured: bool = False

    def metadata(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "enabled": self.enabled,
            "provider": self.provider,
        }
        if self.thinking_budget is not None:
            payload["thinking_budget"] = self.thinking_budget
        if self.preserve_thinking is not None:
            payload["preserve_thinking"] = self.preserve_thinking
        if self.reasoning_effort is not None:
            payload["reasoning_effort"] = self.reasoning_effort
        return payload


def parse_thinking_mode_config(raw: Any, provider_name: str) -> ThinkingModeConfig:
    if raw is None:
        return ThinkingModeConfig()
    if isinstance(raw, bool):
        return ThinkingModeConfig(enabled=raw, configured=True)
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

    reasoning_effort = raw.get("reasoning_effort")
    if reasoning_effort is not None:
        if not isinstance(reasoning_effort, str) or not reasoning_effort.strip():
            raise ThinkingModeConfigError(
                f"Provider '{provider_name}' field 'thinking_mode.reasoning_effort' must be a non-empty string."
            )
        reasoning_effort = reasoning_effort.strip().lower()
        if reasoning_effort not in {"low", "medium", "high", "xhigh", "max"}:
            raise ThinkingModeConfigError(
                f"Provider '{provider_name}' field 'thinking_mode.reasoning_effort' must be one of: "
                "low, medium, high, xhigh, max."
            )

    return ThinkingModeConfig(
        enabled=enabled,
        provider=provider.strip(),
        thinking_budget=thinking_budget,
        preserve_thinking=preserve_thinking,
        reasoning_effort=reasoning_effort,
        configured=True,
    )


def apply_thinking_mode(
    body: dict[str, Any],
    thinking_mode: ThinkingModeConfig,
    model: str,
) -> dict[str, Any]:
    if not thinking_mode.enabled:
        provider = _try_resolve_provider(thinking_mode.provider, model)
        if provider == "deepseek" and _has_explicit_thinking_config(thinking_mode):
            return _apply_deepseek_disabled_mode(body, thinking_mode)
        return body

    provider = _resolve_provider(thinking_mode.provider, model)
    if provider == "qwen":
        return _apply_qwen_thinking_mode(body, thinking_mode)
    if provider == "deepseek":
        return _apply_deepseek_thinking_mode(body, thinking_mode)
    raise ThinkingModeConfigError(f"Unsupported thinking mode provider '{thinking_mode.provider}'.")


def _resolve_provider(provider: str, model: str) -> str:
    resolved = _try_resolve_provider(provider, model)
    if resolved is not None:
        return resolved
    raise ThinkingModeConfigError(
        "thinking_mode.provider is 'auto', but the model family could not be inferred. "
        "Set thinking_mode.provider explicitly."
    )


def _try_resolve_provider(provider: str, model: str) -> str | None:
    normalized = provider.lower().strip()
    if normalized != "auto":
        return normalized
    normalized_model = model.lower().replace("_", "-")
    if normalized_model.startswith("qwen"):
        return "qwen"
    if normalized_model.startswith("deepseek-"):
        return "deepseek"
    return None


def _has_explicit_thinking_config(thinking_mode: ThinkingModeConfig) -> bool:
    return (
        thinking_mode.configured
        or thinking_mode.provider.lower().strip() != "auto"
        or thinking_mode.thinking_budget is not None
        or thinking_mode.preserve_thinking is not None
        or thinking_mode.reasoning_effort is not None
    )


def _apply_qwen_thinking_mode(body: dict[str, Any], thinking_mode: ThinkingModeConfig) -> dict[str, Any]:
    if thinking_mode.reasoning_effort is not None:
        raise ThinkingModeConfigError("thinking_mode.reasoning_effort is only supported for DeepSeek providers.")
    body["enable_thinking"] = True
    if thinking_mode.thinking_budget is not None:
        body["thinking_budget"] = thinking_mode.thinking_budget
    if thinking_mode.preserve_thinking is not None:
        body["preserve_thinking"] = thinking_mode.preserve_thinking
    return body


def _apply_deepseek_thinking_mode(body: dict[str, Any], thinking_mode: ThinkingModeConfig) -> dict[str, Any]:
    _reject_qwen_only_options_for_deepseek(thinking_mode)
    body["thinking"] = {"type": "enabled"}
    if thinking_mode.reasoning_effort is not None:
        body["reasoning_effort"] = thinking_mode.reasoning_effort
    return body


def _apply_deepseek_disabled_mode(body: dict[str, Any], thinking_mode: ThinkingModeConfig) -> dict[str, Any]:
    _reject_qwen_only_options_for_deepseek(thinking_mode)
    if thinking_mode.reasoning_effort is not None:
        raise ThinkingModeConfigError(
            "thinking_mode.reasoning_effort cannot be used when DeepSeek thinking mode is disabled."
        )
    body["thinking"] = {"type": "disabled"}
    body.pop("reasoning_effort", None)
    return body


def _reject_qwen_only_options_for_deepseek(thinking_mode: ThinkingModeConfig) -> None:
    if thinking_mode.thinking_budget is not None:
        raise ThinkingModeConfigError("thinking_mode.thinking_budget is only supported for Qwen providers.")
    if thinking_mode.preserve_thinking is not None:
        raise ThinkingModeConfigError("thinking_mode.preserve_thinking is only supported for Qwen providers.")
