from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentforge.common.file_store import write_json, write_text
from agentforge.common.trace import utc_now_iso


@dataclass(frozen=True)
class SkillVersionInfo:
    skill_slug: str
    version: str
    version_number: int
    skill_root: Path
    skill_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_slug": self.skill_slug,
            "version": self.version,
            "version_number": self.version_number,
            "skill_root": str(self.skill_root),
            "skill_path": str(self.skill_path),
        }


@dataclass(frozen=True)
class WrittenSkillVersion:
    skill_path: Path
    metadata_path: Path
    version: str
    previous_version: str


def parse_skill_version_path(skill_path: Path | str) -> SkillVersionInfo:
    path = Path(skill_path)
    if path.name != "SKILL.md":
        raise ValueError(f"Skill path must point to SKILL.md: {path}")

    version = path.parent.name
    match = re.fullmatch(r"v([1-9][0-9]*)", version)
    if not match:
        raise ValueError(f"Skill path must be under a version directory like v1: {path}")

    skill_root = path.parent.parent
    skill_slug = skill_root.name
    return SkillVersionInfo(
        skill_slug=skill_slug,
        version=version,
        version_number=int(match.group(1)),
        skill_root=skill_root,
        skill_path=path,
    )


def list_skill_versions(skill_root: Path | str) -> list[str]:
    root = Path(skill_root)
    versions: list[tuple[int, str]] = []
    if not root.exists():
        return []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        match = re.fullmatch(r"v([1-9][0-9]*)", child.name)
        if match and (child / "SKILL.md").exists():
            versions.append((int(match.group(1)), child.name))
    return [version for _, version in sorted(versions)]


def next_version(skill_path: Path | str) -> str:
    info = parse_skill_version_path(skill_path)
    highest = info.version_number
    for version in list_skill_versions(info.skill_root):
        highest = max(highest, int(version[1:]))
    return f"v{highest + 1}"


def next_skill_path(skill_path: Path | str) -> Path:
    info = parse_skill_version_path(skill_path)
    return info.skill_root / next_version(info.skill_path) / "SKILL.md"


def write_next_skill_version(
    previous_skill_path: Path | str,
    markdown: str,
    metadata: dict[str, Any],
) -> WrittenSkillVersion:
    previous_info = parse_skill_version_path(previous_skill_path)
    new_version = next_version(previous_info.skill_path)
    new_skill_path = previous_info.skill_root / new_version / "SKILL.md"
    if new_skill_path.exists():
        raise ValueError(f"Refusing to overwrite existing Skill version: {new_skill_path}")

    write_text(new_skill_path, markdown)
    metadata_payload = {
        "skill_slug": previous_info.skill_slug,
        "previous_version": previous_info.version,
        "new_version": new_version,
        "created_at": utc_now_iso(),
        **metadata,
    }
    metadata_path = write_json(new_skill_path.parent / "metadata.json", metadata_payload)
    return WrittenSkillVersion(
        skill_path=new_skill_path,
        metadata_path=metadata_path,
        version=new_version,
        previous_version=previous_info.version,
    )
