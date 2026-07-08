from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentforge.common.trace import utc_now_iso


@dataclass
class WorkflowStepState:
    name: str
    kind: str
    status: str = "running"
    attempt: int = 1
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: str | None = None
    input: Any = None
    output: Any = None
    error: Any = None

    def complete(self, status: str = "completed", output: Any = None, error: Any = None) -> None:
        self.status = status
        self.output = output
        self.error = error
        self.completed_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "attempt": self.attempt,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "input": self.input,
            "output": self.output,
            "error": self.error,
        }


@dataclass
class WorkflowRunState:
    run_id: str
    workflow_id: str
    task_type: str
    status: str = "running"
    current_step: str | None = None
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: str | None = None
    steps: list[WorkflowStepState] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: WorkflowStepState) -> None:
        self.current_step = step.name
        self.steps.append(step)

    def finish(self, status: str) -> None:
        self.status = status
        self.completed_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "task_type": self.task_type,
            "status": self.status,
            "current_step": self.current_step,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "steps": [step.to_dict() for step in self.steps],
            "metadata": self.metadata,
        }
