from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from agentforge.common.llm_client import LLMClient
from agentforge.tasks.handlers.code_analysis import handle_code_analysis_task
from agentforge.tasks.handlers.data_analysis import handle_data_analysis_task
from agentforge.tasks.handlers.document_analysis import handle_document_analysis_task
from agentforge.tasks.handlers.skill_tasks import (
    handle_skill_evolve_task,
    handle_skill_generate_task,
    handle_skill_run_task,
)
from agentforge.tasks.handlers.trace_diagnosis import handle_trace_diagnosis_task
from agentforge.tasks.schemas import TaskRequest, TaskResult, TaskTypeSpec


TaskHandler = Callable[[TaskRequest, Path, LLMClient | None], TaskResult]

_PATH_LIST_SCHEMA = {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1}
_TEXT_OR_PATH_ANY_OF = [
    {"required": ["input"]},
    {"required": ["text"]},
    {"required": ["content"]},
    {"required": ["path"]},
    {"required": ["file_path"]},
    {"required": ["paths"]},
    {"required": ["files"]},
]


TASK_TYPES: dict[str, TaskTypeSpec] = {
    "skill_generate": TaskTypeSpec(
        task_type="skill_generate",
        title="Generate Skill",
        description="Generate a versioned SKILL.md from a requirement.",
        input_schema={
            "type": "object",
            "required": ["input"],
            "properties": {"input": {"type": "string", "minLength": 1}},
        },
    ),
    "skill_run": TaskTypeSpec(
        task_type="skill_run",
        title="Run Skill",
        description="Run a Skill against a single task input.",
        input_schema={
            "type": "object",
            "required": ["input"],
            "properties": {"input": {"type": "string", "minLength": 1}},
        },
        options_schema={
            "type": "object",
            "anyOf": [{"required": ["skill_path"]}, {"required": ["skill_slug"]}],
            "properties": {
                "skill_path": {"type": "string", "minLength": 1},
                "skill_slug": {"type": "string", "minLength": 1},
            },
        },
    ),
    "skill_evolve": TaskTypeSpec(
        task_type="skill_evolve",
        title="Evolve Skill",
        description="Evaluate and rewrite a Skill with a taskset.",
        options_schema={
            "type": "object",
            "required": ["taskset_path"],
            "anyOf": [{"required": ["skill_path"]}, {"required": ["skill_slug"]}],
            "properties": {
                "taskset_path": {"type": "string", "minLength": 1},
                "skill_path": {"type": "string", "minLength": 1},
                "skill_slug": {"type": "string", "minLength": 1},
            },
        },
    ),
    "trace_diagnosis": TaskTypeSpec(
        task_type="trace_diagnosis",
        title="Trace Diagnosis",
        description="Inspect a local trace or run trace and produce a structured diagnosis.",
        input_schema={
            "type": "object",
            "anyOf": [
                {"required": ["trace_file"]},
                {"required": ["trace_path"]},
                {"required": ["run_id"]},
                {"required": ["latest"]},
            ],
            "properties": {
                "trace_file": {"type": "string", "minLength": 1},
                "trace_path": {"type": "string", "minLength": 1},
                "run_id": {"type": "string", "minLength": 1},
                "latest": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
    ),
    "document_analysis": TaskTypeSpec(
        task_type="document_analysis",
        title="Document Analysis",
        description="Analyze local text or Markdown documents with deterministic local checks.",
        input_schema={
            "type": "object",
            "anyOf": _TEXT_OR_PATH_ANY_OF,
            "properties": {
                "input": {"type": "string", "minLength": 1},
                "text": {"type": "string", "minLength": 1},
                "content": {"type": "string", "minLength": 1},
                "path": {"type": "string", "minLength": 1},
                "file_path": {"type": "string", "minLength": 1},
                "paths": _PATH_LIST_SCHEMA,
                "files": _PATH_LIST_SCHEMA,
            },
        },
    ),
    "code_analysis": TaskTypeSpec(
        task_type="code_analysis",
        title="Code Analysis",
        description="Analyze local code snippets or project files with deterministic local checks.",
        input_schema={
            "type": "object",
            "anyOf": [
                {"required": ["input"]},
                {"required": ["code"]},
                {"required": ["text"]},
                {"required": ["path"]},
                {"required": ["file_path"]},
                {"required": ["paths"]},
                {"required": ["files"]},
            ],
            "properties": {
                "input": {"type": "string", "minLength": 1},
                "code": {"type": "string", "minLength": 1},
                "text": {"type": "string", "minLength": 1},
                "path": {"type": "string", "minLength": 1},
                "file_path": {"type": "string", "minLength": 1},
                "paths": _PATH_LIST_SCHEMA,
                "files": _PATH_LIST_SCHEMA,
                "language": {"type": "string"},
            },
        },
    ),
    "data_analysis": TaskTypeSpec(
        task_type="data_analysis",
        title="Data Analysis",
        description="Profile local CSV, TSV, JSON, or JSONL data with deterministic local checks.",
        input_schema={
            "type": "object",
            "anyOf": [
                {"required": ["input"]},
                {"required": ["data"]},
                {"required": ["text"]},
                {"required": ["path"]},
                {"required": ["file_path"]},
                {"required": ["paths"]},
                {"required": ["files"]},
            ],
            "properties": {
                "input": {"type": "string", "minLength": 1},
                "data": {"type": "string", "minLength": 1},
                "text": {"type": "string", "minLength": 1},
                "path": {"type": "string", "minLength": 1},
                "file_path": {"type": "string", "minLength": 1},
                "paths": _PATH_LIST_SCHEMA,
                "files": _PATH_LIST_SCHEMA,
                "format": {"enum": ["csv", "tsv", "json", "jsonl", "ndjson"]},
                "delimiter": {"type": "string"},
            },
        },
    ),
}


_HANDLERS: dict[str, TaskHandler] = {
    "skill_generate": handle_skill_generate_task,
    "skill_run": handle_skill_run_task,
    "skill_evolve": handle_skill_evolve_task,
    "trace_diagnosis": handle_trace_diagnosis_task,
    "code_analysis": handle_code_analysis_task,
    "document_analysis": handle_document_analysis_task,
    "data_analysis": handle_data_analysis_task,
}


def list_task_types() -> list[dict[str, Any]]:
    return [TASK_TYPES[key].to_dict() for key in sorted(TASK_TYPES)]


def route_task(
    request: TaskRequest,
    project_root: Path | str = ".",
    llm_client: LLMClient | None = None,
) -> TaskResult:
    task_type = request.task_type.strip()
    spec = TASK_TYPES.get(task_type)
    if spec is None:
        known = ", ".join(sorted(TASK_TYPES))
        raise ValueError(f"Unsupported task_type: {task_type}. Supported task types: {known}.")
    validation_errors = spec.validate_request(request)
    if validation_errors:
        raise ValueError(f"Invalid task request for {task_type}: {'; '.join(validation_errors)}")
    handler = _HANDLERS.get(task_type)
    if handler is None:
        known = ", ".join(sorted(_HANDLERS))
        raise ValueError(f"Unsupported task_type: {task_type}. Supported executable task types: {known}.")
    return handler(request, Path(project_root).resolve(), llm_client)
