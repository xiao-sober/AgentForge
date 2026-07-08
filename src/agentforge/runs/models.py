from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    task_type: str
    title: str
    status: str
    input: dict[str, Any]
    output: dict[str, Any] | None
    trace_path: str | None
    created_at: str
    updated_at: str
    completed_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task_type": self.task_type,
            "title": self.title,
            "status": self.status,
            "input": self.input,
            "output": self.output,
            "trace_path": self.trace_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }


@dataclass(frozen=True)
class RunStepRecord:
    step_id: str
    run_id: str
    name: str
    kind: str
    status: str
    input: Any | None
    output: Any | None
    error: Any | None
    started_at: str | None
    completed_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "run_id": self.run_id,
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "input": self.input,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    run_id: str
    type: str
    path: str | None
    content_type: str | None
    metadata: dict[str, Any] | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "run_id": self.run_id,
            "type": self.type,
            "path": self.path,
            "content_type": self.content_type,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ToolCallRecord:
    tool_call_id: str
    run_id: str
    step_id: str | None
    tool_name: str
    status: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None
    error: Any | None
    started_at: str
    completed_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_call_id": self.tool_call_id,
            "run_id": self.run_id,
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "status": self.status,
            "arguments": self.arguments,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass(frozen=True)
class HQSReportRecord:
    hqs_id: str
    run_id: str
    scope: str
    average_score: float
    report: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "hqs_id": self.hqs_id,
            "run_id": self.run_id,
            "scope": self.scope,
            "average_score": self.average_score,
            "report": self.report,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class WorkflowCheckpointRecord:
    checkpoint_id: str
    run_id: str
    workflow_id: str
    step_name: str | None
    state: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "step_name": self.step_name,
            "state": self.state,
            "created_at": self.created_at,
        }
