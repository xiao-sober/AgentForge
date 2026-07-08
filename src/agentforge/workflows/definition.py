from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class WorkflowStepDefinition:
    name: str
    kind: str = "workflow_step"
    description: str = ""
    retry_policy: dict[str, Any] = field(default_factory=dict)
    artifact_policy: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Workflow step name cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "retry_policy": self.retry_policy,
            "artifact_policy": self.artifact_policy,
        }


@dataclass(frozen=True)
class WorkflowDefinition:
    workflow_id: str
    task_type: str
    steps: list[WorkflowStepDefinition] = field(default_factory=list)
    stop_conditions: dict[str, Any] = field(default_factory=dict)
    retry_policy: dict[str, Any] = field(default_factory=dict)
    artifact_policy: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.workflow_id.strip():
            raise ValueError("Workflow id cannot be empty.")
        if not self.task_type.strip():
            raise ValueError("Workflow task_type cannot be empty.")

    @classmethod
    def from_step_names(
        cls,
        workflow_id: str,
        task_type: str,
        step_names: list[str] | tuple[str, ...] | None = None,
        stop_conditions: dict[str, Any] | None = None,
        retry_policy: dict[str, Any] | None = None,
        artifact_policy: dict[str, Any] | None = None,
    ) -> "WorkflowDefinition":
        return cls(
            workflow_id=workflow_id,
            task_type=task_type,
            steps=[WorkflowStepDefinition(name=name) for name in (step_names or [])],
            stop_conditions=stop_conditions or {},
            retry_policy=retry_policy or {},
            artifact_policy=artifact_policy or {},
        )

    def step_for(self, name: str) -> WorkflowStepDefinition | None:
        for step in self.steps:
            if step.name == name:
                return step
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "task_type": self.task_type,
            "steps": [step.to_dict() for step in self.steps],
            "stop_conditions": self.stop_conditions,
            "retry_policy": self.retry_policy,
            "artifact_policy": self.artifact_policy,
        }
