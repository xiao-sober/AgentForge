from __future__ import annotations

from typing import Any

from agentforge.runs.service import RunService


class WorkflowCheckpointStore:
    def __init__(self, run_service: RunService) -> None:
        self.run_service = run_service

    def save(
        self,
        run_id: str,
        workflow_id: str,
        state: dict[str, Any],
        step_name: str | None = None,
    ) -> None:
        self.run_service.record_workflow_checkpoint(
            run_id=run_id,
            workflow_id=workflow_id,
            step_name=step_name,
            state=state,
        )

    def list(self, run_id: str) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self.run_service.repository.list_workflow_checkpoints(run_id)]
