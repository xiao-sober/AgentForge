from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from agentforge.common.llm_client import LLMProviderError
from agentforge.providers.config import ModelProviderConfig, ProviderConfigError
from agentforge.providers.thinking_modes import ThinkingModeConfigError, apply_thinking_mode


@dataclass(frozen=True)
class OpenAICompatibleChatClient:
    config: ModelProviderConfig

    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        body.update(self.config.extra_body)
        try:
            apply_thinking_mode(body, self.config.thinking_mode, self.config.model)
        except ThinkingModeConfigError as exc:
            raise LLMProviderError(str(exc)) from exc

        request = Request(
            url=f"{self.config.base_url}/chat/completions",
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
            raise LLMProviderError(
                f"Provider '{self.config.name}' returned HTTP {exc.code}: {detail[:1000]}"
            ) from exc
        except URLError as exc:
            raise LLMProviderError(f"Provider '{self.config.name}' request failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise LLMProviderError(f"Provider '{self.config.name}' returned invalid JSON.") from exc

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(f"Provider '{self.config.name}' returned an unexpected response shape.") from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMProviderError(f"Provider '{self.config.name}' returned empty content.")
        return content

    def metadata(self) -> dict[str, object]:
        return self.config.metadata()


def create_llm_client(config: ModelProviderConfig) -> OpenAICompatibleChatClient:
    if config.provider_type != "openai_compatible":
        raise ProviderConfigError(
            f"Unsupported provider type '{config.provider_type}'. Currently supported: openai_compatible."
        )
    return OpenAICompatibleChatClient(config=config)
