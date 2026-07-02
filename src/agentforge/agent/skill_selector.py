from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentforge.agent.intent_parser import Intent
from agentforge.skill_evolver.version_manager import list_skill_versions
from agentforge.skill_generator.skill_schema import validate_skill


@dataclass(frozen=True)
class SkillCandidate:
    skill_slug: str
    version: str
    skill_path: Path
    title: str
    score: float
    reasons: list[str]
    source: str = "local"
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_slug": self.skill_slug,
            "version": self.version,
            "skill_path": str(self.skill_path),
            "title": self.title,
            "score": self.score,
            "reasons": self.reasons,
            "source": self.source,
            "metadata": self.metadata or {},
        }


def list_available_skills(project_root: Path | str = ".") -> list[dict[str, Any]]:
    root = Path(project_root).resolve()
    skills: list[dict[str, Any]] = []
    for source, search_root in _search_roots(root):
        if not search_root.exists():
            continue
        for skill_dir in sorted(child for child in search_root.iterdir() if child.is_dir()):
            versions = list_skill_versions(skill_dir)
            if not versions:
                continue
            latest_version = versions[-1]
            latest_path = skill_dir / latest_version / "SKILL.md"
            skills.append(_build_skill_listing(skill_dir, latest_path, latest_version, versions, source, root))
    return skills


def select_skill(intent: Intent, project_root: Path | str = ".") -> SkillCandidate | None:
    root = Path(project_root).resolve()
    candidates: list[SkillCandidate] = []
    semantic_memory = _load_semantic_memory(root)
    for skill in _list_skill_version_candidates(root):
        path = Path(str(skill["skill_path"]))
        markdown = path.read_text(encoding="utf-8")
        metadata = dict(skill.get("metadata", {}))
        validation = metadata.get("validation", {})
        if isinstance(validation, dict) and validation.get("valid") is False:
            continue
        semantic = semantic_memory.get(str(skill["skill_slug"]), {})
        score, reasons = _score_skill(intent, skill, markdown, metadata, semantic)
        if score > 0:
            candidates.append(
                SkillCandidate(
                    skill_slug=str(skill["skill_slug"]),
                    version=str(skill["version"]),
                    skill_path=path,
                    title=str(skill["title"]),
                    score=score,
                    reasons=reasons,
                    source=str(skill.get("source", "local")),
                    metadata=metadata,
                )
            )
    if not candidates:
        return None
    candidates.sort(key=lambda candidate: (candidate.score, _version_number(candidate.version)), reverse=True)
    best = candidates[0]
    return best if best.score >= 1.0 else None


def _list_skill_version_candidates(root: Path) -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    for source, search_root in _search_roots(root):
        if not search_root.exists():
            continue
        for skill_dir in sorted(child for child in search_root.iterdir() if child.is_dir()):
            versions = list_skill_versions(skill_dir)
            for version in versions:
                skill_path = skill_dir / version / "SKILL.md"
                metadata = _extract_metadata(skill_dir.name, skill_path, skill_path.read_text(encoding="utf-8"), source)
                skills.append(
                    {
                        "skill_slug": skill_dir.name,
                        "version": version,
                        "skill_path": str(skill_path),
                        "title": metadata["title"],
                        "source": source,
                        "relative_path": _relative_or_absolute(skill_path, root),
                        "metadata": metadata,
                    }
                )
    return skills


def _score_skill(
    intent: Intent,
    skill: dict[str, Any],
    markdown: str,
    metadata: dict[str, Any],
    semantic: dict[str, Any],
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0
    skill_slug = str(skill["skill_slug"])
    searchable = [
        skill_slug,
        str(skill.get("title", "")),
        str(metadata.get("purpose", "")),
        str(metadata.get("when_to_use", "")),
        " ".join(metadata.get("outputs", [])) if isinstance(metadata.get("outputs"), list) else "",
        " ".join(metadata.get("tags", [])) if isinstance(metadata.get("tags"), list) else "",
        str(semantic.get("summary", "")) if isinstance(semantic, dict) else "",
        markdown,
    ]
    haystack = "\n".join(searchable).lower()
    query_tokens = set(_tokens(intent.query))
    haystack_tokens = set(_tokens(haystack))

    if intent.skill_hint:
        if intent.skill_hint == skill_slug:
            score += 6.0
            reasons.append("skill_hint_match")
        else:
            score -= 1.0
            reasons.append("skill_hint_mismatch")
    overlap = len(query_tokens & haystack_tokens)
    if overlap:
        score += min(3.0, overlap * 0.35)
        reasons.append("token_overlap")
    tag_overlap = query_tokens & set(_tokens(" ".join(metadata.get("tags", [])) if isinstance(metadata.get("tags"), list) else ""))
    if tag_overlap:
        score += min(1.5, len(tag_overlap) * 0.5)
        reasons.append("tag_overlap")
    hqs_average = metadata.get("hqs_average")
    if isinstance(hqs_average, (int, float)) and hqs_average >= 4.0:
        score += 0.5
        reasons.append("high_hqs_metadata")
    if isinstance(semantic, dict) and semantic.get("best_version") == skill.get("version"):
        score += 0.5
        reasons.append("semantic_best_version")
    if skill.get("source") == "sample":
        score -= 0.25
        reasons.append("sample_fallback")
    if intent.requires_skill:
        score += 0.5
        reasons.append("requires_skill")
    return round(score, 2), reasons


def _search_roots(root: Path) -> list[tuple[str, Path]]:
    return [("local", root / "skills"), ("sample", root / "examples" / "skills")]


def _build_skill_listing(
    skill_dir: Path,
    latest_path: Path,
    latest_version: str,
    versions: list[str],
    source: str,
    project_root: Path,
) -> dict[str, Any]:
    markdown = latest_path.read_text(encoding="utf-8")
    metadata = _extract_metadata(skill_dir.name, latest_path, markdown, source)
    return {
        "skill_slug": skill_dir.name,
        "versions": versions,
        "latest_version": latest_version,
        "latest_skill_path": str(latest_path),
        "title": metadata["title"],
        "source": source,
        "relative_path": _relative_or_absolute(latest_path, project_root),
        "metadata": metadata,
    }


def _extract_metadata(skill_slug: str, path: Path, markdown: str, source: str) -> dict[str, Any]:
    sections = _extract_sections(markdown)
    metadata_path = path.parent / "metadata.json"
    stored_metadata = _read_json(metadata_path) if metadata_path.exists() else {}
    title = _extract_title_from_markdown(markdown) or skill_slug
    outputs = _bullet_values(sections.get("Outputs", ""))
    tags = _dedupe(
        _tokens(skill_slug)
        + _tokens(title)
        + _tokens(sections.get("Purpose", ""))
        + _tokens(" ".join(outputs))
        + _string_list(stored_metadata.get("tags"))
    )
    return {
        "title": title,
        "purpose": sections.get("Purpose", "").strip(),
        "when_to_use": sections.get("When to Use", "").strip(),
        "outputs": outputs,
        "tags": tags,
        "source": source,
        "validation": validate_skill(markdown).to_dict(),
        "version_metadata": stored_metadata,
        "hqs_average": stored_metadata.get("hqs_average"),
    }


def _extract_sections(markdown: str) -> dict[str, str]:
    lines = markdown.splitlines()
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def _extract_title(path: Path) -> str:
    if not path.exists():
        return path.parent.parent.name
    title = _extract_title_from_markdown(path.read_text(encoding="utf-8"))
    return title or path.parent.parent.name


def _extract_title_from_markdown(markdown: str) -> str | None:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _bullet_values(section: str) -> list[str]:
    values = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            values.append(stripped[2:].strip())
    return values


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_semantic_memory(root: Path) -> dict[str, Any]:
    path = root / "data" / "memory" / "semantic_memory.json"
    return _read_json(path) if path.exists() else {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return []


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _tokens(text: str) -> list[str]:
    normalized = re.sub(r"[^A-Za-z0-9]+", " ", text.lower().replace("_", " "))
    stopwords = {"the", "and", "for", "with", "this", "that", "from", "into", "about", "please", "skill"}
    return [token for token in normalized.split() if len(token) >= 3 and token not in stopwords]


def _version_number(version: str) -> int:
    match = re.fullmatch(r"v([1-9][0-9]*)", version)
    return int(match.group(1)) if match else 0


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
