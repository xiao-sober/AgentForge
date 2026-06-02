from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from agentforge.common.trace import utc_now_iso, write_trace
from agentforge.memory.stores import append_jsonl, read_json_object, read_jsonl, write_json_object

_MISSING = object()
_MEMORY_MANAGER_LOCK = RLock()


@dataclass(frozen=True)
class MemoryPaths:
    root: Path
    working: Path
    episodes: Path
    semantic: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "root": str(self.root),
            "working": str(self.working),
            "episodes": str(self.episodes),
            "semantic": str(self.semantic),
        }


class MemoryManager:
    """Three-layer local memory backed by readable JSON and JSONL files."""

    def __init__(self, project_root: Path | str = ".", trace_updates: bool = True) -> None:
        self.project_root = Path(project_root).resolve()
        memory_root = self.project_root / "data" / "memory"
        self.paths = MemoryPaths(
            root=memory_root,
            working=memory_root / "working_memory.json",
            episodes=memory_root / "episodes.jsonl",
            semantic=memory_root / "semantic_memory.json",
        )
        self.trace_updates = trace_updates

    def add_working_memory(self, key_or_entry: str | dict[str, Any], value: Any = _MISSING) -> dict[str, Any]:
        with _MEMORY_MANAGER_LOCK:
            memory = self.get_working_memory()
            if isinstance(key_or_entry, dict) and value is _MISSING:
                updates = key_or_entry
            elif isinstance(key_or_entry, str) and value is not _MISSING:
                updates = {key_or_entry: value}
            else:
                raise ValueError("add_working_memory requires a dict or a key and value.")

            memory.update(updates)
            memory["updated_at"] = utc_now_iso()
            write_json_object(self.paths.working, memory)
        self._trace_update("working_memory", {"updated_keys": sorted(updates.keys())})
        return memory

    def get_working_memory(self) -> dict[str, Any]:
        return read_json_object(self.paths.working, default={})

    def save_episode(self, episode: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(episode, dict):
            raise ValueError("Episode memory must be a JSON object.")
        record = {
            "episode_id": str(episode.get("episode_id") or f"episode_{uuid4().hex}"),
            "created_at": str(episode.get("created_at") or utc_now_iso()),
            **episode,
        }
        append_jsonl(self.paths.episodes, record)
        self._trace_update("episodic_memory", {"episode_id": record["episode_id"]})
        return record

    def search_episodes(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        records = read_jsonl(self.paths.episodes)
        return _rank_records(records, query, limit)

    def upsert_semantic_memory(self, key: str, value: dict[str, Any]) -> dict[str, Any]:
        if not key.strip():
            raise ValueError("Semantic memory key cannot be empty.")
        if not isinstance(value, dict):
            raise ValueError("Semantic memory value must be a JSON object.")

        with _MEMORY_MANAGER_LOCK:
            semantic = read_json_object(self.paths.semantic, default={})
            existing = semantic.get(key, {})
            if not isinstance(existing, dict):
                existing = {}
            record = {
                **existing,
                **value,
                "key": key,
                "updated_at": utc_now_iso(),
            }
            semantic[key] = record
            write_json_object(self.paths.semantic, semantic)
        self._trace_update("semantic_memory", {"key": key})
        return record

    def search_semantic_memory(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        semantic = read_json_object(self.paths.semantic, default={})
        records = [value for value in semantic.values() if isinstance(value, dict)]
        return _rank_records(records, query, limit)

    def retrieve_context_for_task(self, task_text: str, limit: int = 5) -> dict[str, Any]:
        return {
            "working_memory": self.get_working_memory(),
            "episodes": self.search_episodes(task_text, limit=limit),
            "semantic_memory": self.search_semantic_memory(task_text, limit=limit),
        }

    def summary(self) -> dict[str, Any]:
        semantic = read_json_object(self.paths.semantic, default={})
        episodes = read_jsonl(self.paths.episodes)
        return {
            "paths": self.paths.to_dict(),
            "working_memory": self.get_working_memory(),
            "episode_count": len(episodes),
            "semantic_count": len(semantic),
            "latest_episodes": episodes[-10:],
            "semantic_memory": semantic,
        }

    def _trace_update(self, layer: str, output: dict[str, Any]) -> None:
        if not self.trace_updates:
            return
        write_trace(
            project_root=self.project_root,
            trace_type="memory_update",
            input_data={"layer": layer},
            output=output,
            steps=[{"name": "write_memory", "status": "completed", "layer": layer}],
            artifacts=[{"type": layer, "path": _relative_or_absolute(self.paths.root, self.project_root)}],
            errors=[],
        )


def _rank_records(records: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    query_tokens = set(_tokens(query))
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, record in enumerate(records):
        record_text = _stringify(record)
        record_tokens = set(_tokens(record_text))
        score = len(query_tokens & record_tokens) if query_tokens else 0
        if score > 0 or not query_tokens:
            scored.append((score, index, record))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [record for _, _, record in scored[: max(0, limit)]]


def _tokens(text: str) -> list[str]:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in text)
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "into",
        "about",
        "please",
        "agentforge",
    }
    return [token for token in normalized.split() if len(token) >= 3 and token not in stopwords]


def _stringify(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {_stringify(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(_stringify(item) for item in value)
    return str(value)


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
