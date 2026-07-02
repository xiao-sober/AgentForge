from __future__ import annotations

import difflib
from pathlib import Path

from agentforge.common.file_store import write_text


def create_unified_diff(
    old_markdown: str,
    new_markdown: str,
    old_label: str,
    new_label: str,
) -> str:
    lines = difflib.unified_diff(
        old_markdown.splitlines(),
        new_markdown.splitlines(),
        fromfile=old_label,
        tofile=new_label,
        lineterm="",
    )
    diff = "\n".join(lines)
    return diff if diff.endswith("\n") else diff + "\n"


def write_diff(path: Path, diff_text: str) -> Path:
    return write_text(path, diff_text)
