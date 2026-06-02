from __future__ import annotations

import json
from threading import RLock
from pathlib import Path
from typing import Any

from agentforge.common.file_store import ensure_directory, write_json

_MEMORY_LOCK = RLock()


def read_json_object(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    with _MEMORY_LOCK:
        if not path.exists():
            return dict(default or {})
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Memory JSON is invalid: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Memory JSON must be an object: {path}")
    return payload


def write_json_object(path: Path, payload: dict[str, Any]) -> Path:
    with _MEMORY_LOCK:
        return write_json(path, payload)


def append_jsonl(path: Path, payload: dict[str, Any]) -> Path:
    with _MEMORY_LOCK:
        ensure_directory(path.parent)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with _MEMORY_LOCK:
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Memory JSONL is invalid at {path}:{line_number}") from exc
            if isinstance(payload, dict):
                records.append(payload)
    return records
