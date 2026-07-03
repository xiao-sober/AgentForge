from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import agentforge
from agentforge.providers import ProviderConfigError, create_llm_client, load_provider_config


def build_version_report(project_root: Path | str = ".") -> dict[str, Any]:
    root = Path(project_root).resolve()
    return {
        "name": "agentforge",
        "version": agentforge.__version__,
        "project_root": str(root),
    }


def build_config_report(project_root: Path | str = ".", provider_config: Path | str = "config/providers.json") -> dict[str, Any]:
    root = Path(project_root).resolve()
    config_path = _resolve(root, Path(provider_config))
    example_path = root / "config" / "providers.example.json"
    report: dict[str, Any] = {
        "project_root": str(root),
        "provider_config_path": str(config_path),
        "provider_config_exists": config_path.exists(),
        "provider_example_exists": example_path.exists(),
        "default_provider": None,
        "providers": [],
        "errors": [],
    }

    if not config_path.exists():
        report["status"] = "local_only"
        report["message"] = "Provider config is absent; local deterministic mode is available."
        return report

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report["status"] = "invalid"
        report["errors"].append(f"Provider config is invalid JSON: {exc}")
        return report

    if not isinstance(raw, dict):
        report["status"] = "invalid"
        report["errors"].append("Provider config must be a JSON object.")
        return report

    report["default_provider"] = raw.get("default_provider")
    providers = raw.get("providers", {})
    if not isinstance(providers, dict):
        report["status"] = "invalid"
        report["errors"].append("Provider config field 'providers' must be an object.")
        return report

    for name, provider in providers.items():
        if not isinstance(provider, dict):
            report["providers"].append({"name": str(name), "valid": False, "error": "provider entry must be an object"})
            continue
        report["providers"].append(_redacted_provider_summary(str(name), provider))

    try:
        selected = load_provider_config(config_path)
        report["selected_provider"] = create_llm_client(selected).metadata()
    except ProviderConfigError as exc:
        report["errors"].append(str(exc))

    report["status"] = "ok" if not report["errors"] else "invalid"
    return report


def build_health_report(project_root: Path | str = ".") -> dict[str, Any]:
    root = Path(project_root).resolve()
    directories = []
    for relative in ["skills", "examples/skills", "tasksets", "runs", "traces", "data/memory", "config"]:
        path = root / relative
        directories.append(
            {
                "path": relative,
                "exists": path.exists(),
                "is_dir": path.is_dir(),
                "writable": _is_writable_directory(path),
            }
        )

    config = build_config_report(root)
    has_samples = (root / "examples" / "skills").exists() and any((root / "examples" / "skills").glob("*/*/SKILL.md"))
    blocking = [
        item["path"]
        for item in directories
        if item["path"] in {"runs", "traces", "data/memory"} and item["exists"] and not item["writable"]
    ]
    status = "ok" if not blocking else "degraded"
    return {
        "status": status,
        "version": build_version_report(root),
        "directories": directories,
        "config": config,
        "samples_available": has_samples,
        "blocking_issues": blocking,
    }


def _redacted_provider_summary(name: str, provider: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "type": provider.get("type", "openai_compatible"),
        "base_url": provider.get("base_url"),
        "model": provider.get("model"),
        "has_api_key": bool(provider.get("api_key")),
        "api_key_env": provider.get("api_key_env"),
        "timeout_seconds": provider.get("timeout_seconds"),
        "thinking_mode": _redact(provider.get("thinking_mode")),
    }


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("<redacted>" if "key" in key.lower() or "secret" in key.lower() else _redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _is_writable_directory(path: Path) -> bool:
    target = path if path.exists() else path.parent
    return target.exists() and target.is_dir()


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path
