from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Task:
    task_id: str
    input: str
    expected_output: Any = None
    criteria: list[str] | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["criteria"] = self.criteria or []
        payload["metadata"] = self.metadata or {}
        return payload


@dataclass(frozen=True)
class TaskSet:
    name: str
    tasks: list[Task]
    description: str = ""
    source_path: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "source_path": self.source_path,
            "metadata": self.metadata or {},
            "tasks": [task.to_dict() for task in self.tasks],
        }


def load_taskset(path: Path | str) -> TaskSet:
    taskset_path = Path(path)
    if not taskset_path.exists():
        raise ValueError(f"Task set not found: {taskset_path}")

    payload = _load_payload(taskset_path)
    return _parse_taskset_payload(payload, taskset_path)


def load_taskset_from_text(text: str, source_path: str = "<stdin>", file_format: str = "json") -> TaskSet:
    payload = _load_payload_from_text(text, source_path=source_path, file_format=file_format)
    return _parse_taskset_payload(payload, Path(source_path))


def _load_payload(path: Path) -> Any:
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Task set is not valid JSON: {path}") from exc

    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ValueError("YAML task sets require PyYAML. Use JSON for the local MVP.") from exc
        return yaml.safe_load(path.read_text(encoding="utf-8-sig"))

    raise ValueError(f"Unsupported task set format '{path.suffix}'. Use .json, .yaml, or .yml.")


def _load_payload_from_text(text: str, source_path: str, file_format: str) -> Any:
    normalized_format = file_format.lower().lstrip(".")
    if normalized_format == "json":
        try:
            return json.loads(text.lstrip("\ufeff"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Task set is not valid JSON: {source_path}") from exc
    if normalized_format in {"yaml", "yml"}:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ValueError("YAML task sets require PyYAML. Use JSON for the local MVP.") from exc
        return yaml.safe_load(text.lstrip("\ufeff"))
    raise ValueError(f"Unsupported task set format '{file_format}'. Use json, yaml, or yml.")


def _parse_taskset_payload(payload: Any, path: Path) -> TaskSet:
    if isinstance(payload, list):
        raw_tasks = payload
        name = path.stem
        description = ""
    elif isinstance(payload, dict):
        raw_tasks = payload.get("tasks")
        name = str(payload.get("name") or path.stem)
        description = str(payload.get("description") or "")
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("Task set metadata must be an object when provided.")
    else:
        raise ValueError("Task set must be a JSON object with a 'tasks' list or a task list.")
    if isinstance(payload, list):
        metadata = {}

    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ValueError("Task set must contain a non-empty 'tasks' list.")

    tasks = [_parse_task(raw_task, index) for index, raw_task in enumerate(raw_tasks, start=1)]
    _validate_unique_task_ids(tasks)
    return TaskSet(name=name, description=description, tasks=tasks, source_path=str(path), metadata=metadata)


def _parse_task(raw_task: Any, index: int) -> Task:
    if isinstance(raw_task, str):
        return Task(task_id=f"task_{index:03d}", input=raw_task, criteria=[], metadata={})
    if not isinstance(raw_task, dict):
        raise ValueError(f"Task #{index} must be an object or string.")

    task_input = _first_present_string(raw_task, ["input", "prompt", "requirement", "content"])
    if not task_input:
        raise ValueError(f"Task #{index} must include a non-empty input, prompt, requirement, or content field.")

    task_id = str(raw_task.get("id") or raw_task.get("task_id") or f"task_{index:03d}").strip()
    expected_output = raw_task.get("expected_output", raw_task.get("expected", raw_task.get("expected_outputs")))
    criteria = _string_list(raw_task.get("criteria", raw_task.get("quality_criteria", [])))
    known_fields = {
        "id",
        "task_id",
        "input",
        "prompt",
        "requirement",
        "content",
        "expected_output",
        "expected",
        "expected_outputs",
        "criteria",
        "quality_criteria",
    }
    metadata = {key: value for key, value in raw_task.items() if key not in known_fields}
    return Task(
        task_id=task_id or f"task_{index:03d}",
        input=task_input,
        expected_output=expected_output,
        criteria=criteria,
        metadata=metadata,
    )


def _first_present_string(payload: dict[str, Any], names: list[str]) -> str:
    for name in names:
        value = payload.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, str) and item.strip():
                result.append(item.strip())
            elif item is not None:
                result.append(str(item))
        return result
    return [str(value)]


def _validate_unique_task_ids(tasks: list[Task]) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for task in tasks:
        if task.task_id in seen:
            duplicates.append(task.task_id)
        seen.add(task.task_id)
    if duplicates:
        raise ValueError("Task set contains duplicate task ids: " + ", ".join(sorted(set(duplicates))))
