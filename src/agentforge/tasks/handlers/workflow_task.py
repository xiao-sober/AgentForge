from __future__ import annotations

from pathlib import Path
from typing import Any

from agentforge.common.trace import write_trace
from agentforge.tasks.schemas import TaskRequest, TaskResult
from agentforge.workflows import WorkflowRunner


def finalize_workflow_task_result(
    *,
    runner: WorkflowRunner,
    run_id: str,
    request: TaskRequest,
    project_root: Path,
    trace_type: str,
    success_state_key: str,
    failure_output_key: str,
) -> TaskResult:
    detail = runner.run_detail(run_id) or {}
    status = str(detail.get("status") or "failed")
    output = detail.get("output") if isinstance(detail.get("output"), dict) else {}
    state = output.get("state") if isinstance(output.get("state"), dict) else {}
    steps = detail.get("steps") if isinstance(detail.get("steps"), list) else []
    artifacts = state.get("artifacts") if isinstance(state.get("artifacts"), list) else []

    if status == "completed" and isinstance(state.get(success_state_key), dict):
        task_output = state[success_state_key]
        trace_path = write_trace(
            project_root=project_root,
            trace_type=trace_type,
            input_data=request.to_dict(),
            output=task_output,
            steps=steps,
            artifacts=artifacts,
            errors=[],
        )
        runner.record_artifact(
            run_id,
            {"type": "trace", "path": _relative_or_absolute(trace_path, project_root)},
            len(artifacts) + 1,
        )
        runner.complete_run(run_id, task_output, trace_path=trace_path, status="completed")
        return TaskResult(
            task_type=request.task_type,
            status="completed",
            run_id=run_id,
            output=task_output,
            trace_path=trace_path,
            artifacts=artifacts,
            errors=[],
        )

    errors = _errors_from_run_output(output, trace_type)
    failure_output = {failure_output_key: None, "errors": errors}
    trace_path = write_trace(
        project_root=project_root,
        trace_type=trace_type,
        input_data=request.to_dict(),
        output=failure_output,
        steps=steps,
        artifacts=artifacts,
        errors=errors,
    )
    runner.record_artifact(
        run_id,
        {"type": "trace", "path": _relative_or_absolute(trace_path, project_root)},
        len(artifacts) + 1,
    )
    runner.fail_run(run_id, errors, failure_output, trace_path=trace_path)
    return TaskResult(
        task_type=request.task_type,
        status="failed",
        run_id=run_id,
        output=failure_output,
        trace_path=trace_path,
        artifacts=artifacts,
        errors=errors,
    )


def _errors_from_run_output(output: dict[str, Any], trace_type: str) -> list[dict[str, Any]]:
    raw_error = output.get("error")
    if isinstance(raw_error, list):
        return [item for item in raw_error if isinstance(item, dict)]
    if isinstance(raw_error, dict):
        return [raw_error]
    return [
        {
            "error_type": "WorkflowTaskFailed",
            "message": f"{trace_type} workflow failed.",
            "recoverable": False,
        }
    ]


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
