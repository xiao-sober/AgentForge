from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentforge.providers.thinking_modes import ThinkingModeConfig, ThinkingModeConfigError, parse_thinking_mode_config


class ProviderConfigError(ValueError):
    """Raised when the model provider configuration is missing or invalid."""


@dataclass(frozen=True)
class ModelProviderConfig:
    name: str
    provider_type: str
    base_url: str
    model: str
    api_key: str | None = None
    api_key_env: str | None = None
    timeout_seconds: int = 60
    temperature: float = 0.2
    max_tokens: int = 2500
    use_env_proxy: bool = False
    thinking_mode: ThinkingModeConfig = field(default_factory=ThinkingModeConfig)
    headers: dict[str, str] = field(default_factory=dict)
    extra_body: dict[str, Any] = field(default_factory=dict)

    def resolved_api_key(self) -> str:
        direct_key = _resolve_api_key_value(self.api_key)
        if direct_key:
            return direct_key
        if self.api_key_env:
            env_key = os.getenv(self.api_key_env)
            if env_key:
                return env_key
        raise ProviderConfigError(
            f"Provider '{self.name}' is missing an API key. Set api_key or api_key_env in the provider JSON."
        )

    def metadata(self) -> dict[str, object]:
        return {
            "provider": self.name,
            "type": self.provider_type,
            "base_url": self.base_url,
            "model": self.model,
            "timeout_seconds": self.timeout_seconds,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "use_env_proxy": self.use_env_proxy,
            "thinking_mode": self.thinking_mode.metadata(),
        }


def load_provider_config(
    config_path: Path,
    provider_name: str | None = None,
    model_override: str | None = None,
) -> ModelProviderConfig:
    if not config_path.exists():
        raise ProviderConfigError(
            f"Provider config not found: {config_path}. Create it from config/providers.example.json "
            "or run generate-skill with --local-only."
        )

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProviderConfigError(f"Provider config is not valid JSON: {config_path}") from exc

    providers = payload.get("providers")
    if not isinstance(providers, dict) or not providers:
        raise ProviderConfigError("Provider config must contain a non-empty 'providers' object.")

    selected_name = provider_name or payload.get("default_provider")
    if not selected_name:
        raise ProviderConfigError("Provider config must set default_provider or the CLI must pass --provider.")
    if selected_name not in providers:
        raise ProviderConfigError(f"Provider '{selected_name}' was not found in {config_path}.")

    raw = providers[selected_name]
    if not isinstance(raw, dict):
        raise ProviderConfigError(f"Provider '{selected_name}' must be an object.")

    provider_type = str(raw.get("type", "openai_compatible"))
    base_url = _required_string(raw, "base_url", selected_name).rstrip("/")
    model = model_override or _required_string(raw, "model", selected_name)
    timeout_seconds = int(raw.get("timeout_seconds", 60))
    temperature = float(raw.get("temperature", 0.2))
    max_tokens = int(raw.get("max_tokens", 2500))
    use_env_proxy = _optional_bool(raw.get("use_env_proxy", False), "use_env_proxy", selected_name)
    try:
        headers = _string_dict(raw.get("headers", {}), "headers", selected_name)
        api_key = _optional_string(raw.get("api_key"), "api_key", selected_name)
        api_key_env = _optional_string(raw.get("api_key_env"), "api_key_env", selected_name)
        thinking_mode = parse_thinking_mode_config(raw.get("thinking_mode"), selected_name)
        extra_body = raw.get("extra_body", {})
        if not isinstance(extra_body, dict):
            raise ProviderConfigError(f"Provider '{selected_name}' field 'extra_body' must be an object.")
    except ThinkingModeConfigError as exc:
        raise ProviderConfigError(str(exc)) from exc

    return ModelProviderConfig(
        name=selected_name,
        provider_type=provider_type,
        base_url=base_url,
        model=model,
        api_key=api_key,
        api_key_env=api_key_env,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        max_tokens=max_tokens,
        use_env_proxy=use_env_proxy,
        thinking_mode=thinking_mode,
        headers=headers,
        extra_body=extra_body,
    )


def _required_string(raw: dict[str, Any], field_name: str, provider_name: str) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ProviderConfigError(f"Provider '{provider_name}' must set a non-empty '{field_name}'.")
    return value.strip()


def _optional_string(value: Any, field_name: str, provider_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProviderConfigError(f"Provider '{provider_name}' field '{field_name}' must be a string.")
    return value.strip()


def _optional_bool(value: Any, field_name: str, provider_name: str) -> bool:
    if not isinstance(value, bool):
        raise ProviderConfigError(f"Provider '{provider_name}' field '{field_name}' must be a boolean.")
    return value


def _string_dict(value: Any, field_name: str, provider_name: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ProviderConfigError(f"Provider '{provider_name}' field '{field_name}' must be an object.")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ProviderConfigError(f"Provider '{provider_name}' field '{field_name}' must contain string values.")
        result[key] = item
    return result


def _resolve_api_key_value(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    if stripped.lower() in {"replace-me", "your-api-key", "your_api_key", "<api-key>", "api-key-here"}:
        return None

    env_match = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", stripped)
    if env_match:
        return os.getenv(env_match.group(1))

    return stripped
