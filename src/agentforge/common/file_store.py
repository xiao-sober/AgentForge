from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentforge.common.artifact_schema import assert_valid_json_artifact


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_text(path: Path, content: str) -> Path:
    ensure_directory(path.parent)
    path.write_text(content, encoding="utf-8", newline="\n")
    return path


def write_json(path: Path, data: dict[str, Any]) -> Path:
    assert_valid_json_artifact(path, data)
    ensure_directory(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path
