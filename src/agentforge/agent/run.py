from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from agentforge.common.trace import utc_now_iso


AGENT_RUN_PHASES = {
    "received",
    "parsed",
    "memory_retrieved",
    "skill_selected",
    "planned",
    "executing",
    "observing",
    "memory_updated",
    "responding",
    "evaluating",
    "quality_gated",
    "reflecting",
    "reinforcing",
    "saving_memory",
    "completed",
    "failed",
}


@dataclass
class AgentRunStep:
    step_id: str
    name: str
    kind: str
    status: str
    started_at: str
    completed_at: str | None = None
    input: Any = None
    output: Any = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def complete(
        self,
        output: Any = None,
        artifacts: list[dict[str, Any]] | None = None,
        errors: list[dict[str, Any]] | None = None,
        status: str = "completed",
    ) -> None:
        self.status = status
        self.output = output
        self.artifacts = artifacts or []
        self.errors = errors or []
        self.completed_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "input": self.input,
            "output": self.output,
            "artifacts": self.artifacts,
            "errors": self.errors,
        }


@dataclass
class AgentRun:
    run_id: str
    created_at: str
    input: dict[str, Any]
    status: str = "running"
    phase: str = "received"
    stop_reason: str | None = None
    reflection: dict[str, Any] | None = None
    steps: list[AgentRunStep] = field(default_factory=list)
    phase_history: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def create(cls, user_input: str) -> "AgentRun":
        created_at = utc_now_iso()
        return cls(
            run_id=f"run_{uuid4().hex}",
            created_at=created_at,
            input={"message": user_input},
            phase_history=[
                {
                    "phase": "received",
                    "status": "entered",
                    "created_at": created_at,
                    "reason": "run_created",
                    "details": {},
                }
            ],
        )

    def add_step(self, name: str, kind: str, input_data: Any = None) -> AgentRunStep:
        step = AgentRunStep(
            step_id=f"step_{len(self.steps) + 1:03d}",
            name=name,
            kind=kind,
            status="running",
            started_at=utc_now_iso(),
            input=input_data,
        )
        self.steps.append(step)
        return step

    def transition(
        self,
        phase: str,
        status: str = "entered",
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if phase not in AGENT_RUN_PHASES:
            raise ValueError(f"Unsupported Agent run phase: {phase}")
        self.phase = phase
        self.phase_history.append(
            {
                "phase": phase,
                "status": status,
                "created_at": utc_now_iso(),
                "reason": reason,
                "details": details or {},
            }
        )

    def finish(self, status: str, stop_reason: str, reflection: dict[str, Any] | None = None) -> None:
        self.status = status
        self.stop_reason = stop_reason
        self.reflection = reflection
        self.transition("failed" if status == "failed" else "completed", status=status, reason=stop_reason)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "input": self.input,
            "status": self.status,
            "phase": self.phase,
            "phase_history": self.phase_history,
            "stop_reason": self.stop_reason,
            "reflection": self.reflection,
            "steps": [step.to_dict() for step in self.steps],
        }
