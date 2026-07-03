from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from agentforge.common.llm_client import LLMProviderError
from agentforge.providers.config import ModelProviderConfig, ProviderConfigError
from agentforge.providers.thinking_modes import ThinkingModeConfigError, apply_thinking_mode


@dataclass(frozen=True)
class OpenAICompatibleChatClient:
    config: ModelProviderConfig

    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        request_model = _request_model(self.config)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": request_model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        body.update(self.config.extra_body)
        try:
            apply_thinking_mode(body, self.config.thinking_mode, request_model)
        except ThinkingModeConfigError as exc:
            raise LLMProviderError(str(exc)) from exc
        _normalize_provider_body(body, self.config, request_model)

        request = Request(
            url=_chat_completions_url(self.config),
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.resolved_api_key()}",
                "Content-Type": "application/json",
                **self.config.headers,
            },
            method="POST",
        )

        try:
            opener = None if self.config.use_env_proxy else build_opener(ProxyHandler({}))
            open_request = urlopen if opener is None else opener.open
            with open_request(request, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMProviderError(_format_http_error(self.config, exc.code, detail)) from exc
        except URLError as exc:
            raise LLMProviderError(f"Provider '{self.config.name}' request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMProviderError(
                f"Provider '{self.config.name}' request timed out after {self.config.timeout_seconds} seconds."
            ) from exc
        except json.JSONDecodeError as exc:
            raise LLMProviderError(f"Provider '{self.config.name}' returned invalid JSON.") from exc

        return _extract_content(payload, self.config, request_model)

    def metadata(self) -> dict[str, object]:
        return _effective_metadata(self.config)


def create_llm_client(config: ModelProviderConfig) -> OpenAICompatibleChatClient:
    if config.provider_type != "openai_compatible":
        raise ProviderConfigError(
            f"Unsupported provider type '{config.provider_type}'. Currently supported: openai_compatible."
        )
    return OpenAICompatibleChatClient(config=config)


def _effective_metadata(config: ModelProviderConfig) -> dict[str, object]:
    metadata = config.metadata()
    request_model = _request_model(config)
    provider_family = _provider_family(config, request_model)
    metadata["request_model"] = request_model
    metadata["provider_family"] = provider_family
    if provider_family == "deepseek":
        metadata["configured_thinking_mode"] = config.thinking_mode.metadata()
        metadata["thinking_mode"] = _effective_deepseek_thinking_metadata(config, request_model)
    return metadata


_DEEPSEEK_MODEL_ALIASES = {
    "deepseek-v4-pro": "deepseek-v4-pro",
    "deepseek-v4-flash": "deepseek-v4-flash",
    "deepseek-chat": "deepseek-chat",
    "deepseek-reasoner": "deepseek-reasoner",
}

_DEEPSEEK_HTTP_HINTS = {
    400: "invalid request body format; check DeepSeek thinking/tool-call message fields",
    401: "authentication failed; check the DeepSeek API key",
    402: "insufficient balance in the DeepSeek account",
    422: "invalid DeepSeek request parameters",
    429: "DeepSeek rate limit reached",
    500: "DeepSeek server error",
    503: "DeepSeek server overloaded",
}


def _request_model(config: ModelProviderConfig) -> str:
    model = config.model.strip()
    model_key = model.lower().replace("_", "-")
    if model_key.startswith("deepseek-"):
        return _DEEPSEEK_MODEL_ALIASES.get(model_key, model_key)
    return model


def _effective_deepseek_thinking_metadata(config: ModelProviderConfig, request_model: str) -> dict[str, object]:
    thinking_mode = config.thinking_mode
    explicit = _has_explicit_thinking_config(thinking_mode)
    if explicit:
        payload = thinking_mode.metadata()
        payload["provider"] = "deepseek"
        payload["source"] = "explicit_config"
        payload["request_body"] = {
            "thinking": {"type": "enabled" if thinking_mode.enabled else "disabled"},
        }
        if thinking_mode.enabled and thinking_mode.reasoning_effort is not None:
            payload["request_body"]["reasoning_effort"] = thinking_mode.reasoning_effort
        return payload

    if _is_deepseek_v4_model(request_model):
        return {
            "enabled": True,
            "provider": "deepseek",
            "source": "provider_default",
            "request_body": {"thinking": "omitted"},
            "note": "DeepSeek V4 defaults to thinking mode when the request omits the thinking field.",
        }

    payload = thinking_mode.metadata()
    payload["provider"] = "deepseek"
    payload["source"] = "config_default"
    return payload


def _has_explicit_thinking_config(thinking_mode: Any) -> bool:
    return (
        bool(getattr(thinking_mode, "configured", False))
        or str(getattr(thinking_mode, "provider", "auto")).lower().strip() != "auto"
        or getattr(thinking_mode, "thinking_budget", None) is not None
        or getattr(thinking_mode, "preserve_thinking", None) is not None
        or getattr(thinking_mode, "reasoning_effort", None) is not None
    )


def _is_deepseek_v4_model(model: str) -> bool:
    normalized = model.lower().replace("_", "-")
    return normalized in {"deepseek-v4-pro", "deepseek-v4-flash"} or normalized.startswith("deepseek-v4-")


def _normalize_provider_body(body: dict[str, Any], config: ModelProviderConfig, request_model: str) -> None:
    if _provider_family(config, request_model) != "deepseek":
        return

    # DeepSeek V4 thinking mode ignores sampling controls. Omitting them keeps traces closer to the
    # provider contract and avoids implying that temperature affected a reasoning run.
    if _deepseek_thinking_enabled_or_default(body):
        body.pop("temperature", None)


def _deepseek_thinking_enabled_or_default(body: dict[str, Any]) -> bool:
    thinking = body.get("thinking")
    if not isinstance(thinking, dict):
        return True
    return str(thinking.get("type", "enabled")).lower().strip() != "disabled"


def _chat_completions_url(config: ModelProviderConfig) -> str:
    base_url = config.base_url.rstrip("/")
    if _is_official_deepseek_base_url(base_url):
        parsed = urlparse(base_url)
        if parsed.path.rstrip("/") == "/v1":
            parsed = parsed._replace(path="", params="", query="", fragment="")
            base_url = urlunparse(parsed).rstrip("/")
    return f"{base_url}/chat/completions"


def _provider_family(config: ModelProviderConfig, request_model: str | None = None) -> str:
    model = (request_model or config.model).lower().replace("_", "-")
    if model.startswith("deepseek-") or _is_official_deepseek_base_url(config.base_url):
        return "deepseek"
    if model.startswith("qwen"):
        return "qwen"
    return "generic"


def _is_official_deepseek_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == "api.deepseek.com"


def _format_http_error(config: ModelProviderConfig, status_code: int, detail: str) -> str:
    hint = None
    if _provider_family(config) == "deepseek":
        hint = _DEEPSEEK_HTTP_HINTS.get(status_code)
    if hint:
        return f"Provider '{config.name}' returned HTTP {status_code} ({hint}): {detail[:1000]}"
    return f"Provider '{config.name}' returned HTTP {status_code}: {detail[:1000]}"


def _extract_content(payload: dict[str, Any], config: ModelProviderConfig, request_model: str) -> str:
    try:
        choice = payload["choices"][0]
        message = choice["message"]
        content = message["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMProviderError(f"Provider '{config.name}' returned an unexpected response shape.") from exc

    finish_reason = choice.get("finish_reason")
    if _provider_family(config, request_model) == "deepseek":
        if finish_reason == "content_filter":
            raise LLMProviderError(f"Provider '{config.name}' returned no final content because content was filtered.")
        if finish_reason == "insufficient_system_resource":
            raise LLMProviderError(
                f"Provider '{config.name}' request was interrupted by DeepSeek insufficient system resources."
            )

    if not isinstance(content, str) or not content.strip():
        reasoning_content = message.get("reasoning_content") if isinstance(message, dict) else None
        if _provider_family(config, request_model) == "deepseek" and isinstance(reasoning_content, str):
            if reasoning_content.strip():
                raise LLMProviderError(
                    f"Provider '{config.name}' returned reasoning_content but no final answer content."
                )
        raise LLMProviderError(f"Provider '{config.name}' returned empty content.")
    return content
