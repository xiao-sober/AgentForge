from __future__ import annotations

import json
from contextlib import closing
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from agentforge.common.trace import utc_now_iso
from agentforge.runs.models import (
    ArtifactRecord,
    HQSReportRecord,
    RunRecord,
    RunStepRecord,
    ToolCallRecord,
    WorkflowCheckpointRecord,
)
from agentforge.storage import SQLiteStore


class RunRepository:
    def __init__(self, project_root: Path | str = ".", db_path: Path | str | None = None) -> None:
        self.store = SQLiteStore(project_root=project_root, db_path=db_path)

    def initialize(self) -> Path:
        return self.store.initialize()

    def create_run(
        self,
        run_id: str,
        task_type: str,
        title: str,
        input_data: dict[str, Any],
        status: str = "queued",
        created_at: str | None = None,
    ) -> RunRecord:
        now = created_at or utc_now_iso()
        with closing(self.store.connect()) as connection:
            connection.execute(
                """
                INSERT INTO runs (
                  run_id, task_type, title, status, input_json, output_json,
                  trace_path, created_at, updated_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?, NULL)
                """,
                (run_id, task_type, title, status, _json_text(input_data), now, now),
            )
            connection.commit()
        return self.get_run(run_id)  # type: ignore[return-value]

    def upsert_run(
        self,
        run_id: str,
        task_type: str,
        title: str,
        status: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any] | None = None,
        trace_path: str | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
        completed_at: str | None = None,
    ) -> RunRecord:
        now = updated_at or utc_now_iso()
        first_created = created_at or now
        with closing(self.store.connect()) as connection:
            connection.execute(
                """
                INSERT INTO runs (
                  run_id, task_type, title, status, input_json, output_json,
                  trace_path, created_at, updated_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                  task_type = excluded.task_type,
                  title = excluded.title,
                  status = excluded.status,
                  input_json = excluded.input_json,
                  output_json = excluded.output_json,
                  trace_path = excluded.trace_path,
                  updated_at = excluded.updated_at,
                  completed_at = excluded.completed_at
                """,
                (
                    run_id,
                    task_type,
                    title,
                    status,
                    _json_text(input_data),
                    _json_text(output_data) if output_data is not None else None,
                    trace_path,
                    first_created,
                    now,
                    completed_at,
                ),
            )
            connection.commit()
        return self.get_run(run_id)  # type: ignore[return-value]

    def update_run_status(
        self,
        run_id: str,
        status: str,
        output_data: dict[str, Any] | None = None,
        trace_path: str | None = None,
        completed_at: str | None = None,
    ) -> RunRecord:
        now = utc_now_iso()
        with closing(self.store.connect()) as connection:
            connection.execute(
                """
                UPDATE runs
                SET status = ?, output_json = COALESCE(?, output_json), trace_path = COALESCE(?, trace_path),
                    updated_at = ?, completed_at = COALESCE(?, completed_at)
                WHERE run_id = ?
                """,
                (
                    status,
                    _json_text(output_data) if output_data is not None else None,
                    trace_path,
                    now,
                    completed_at,
                    run_id,
                ),
            )
            connection.commit()
        return self.get_run(run_id)  # type: ignore[return-value]

    def add_run_step(
        self,
        step_id: str,
        run_id: str,
        name: str,
        kind: str,
        status: str,
        input_data: Any | None = None,
        output_data: Any | None = None,
        error_data: Any | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> RunStepRecord:
        with closing(self.store.connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO run_steps (
                  step_id, run_id, name, kind, status, input_json, output_json,
                  error_json, started_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    step_id,
                    run_id,
                    name,
                    kind,
                    status,
                    _json_text(input_data) if input_data is not None else None,
                    _json_text(output_data) if output_data is not None else None,
                    _json_text(error_data) if error_data is not None else None,
                    started_at,
                    completed_at,
                ),
            )
            connection.commit()
        return self.list_run_steps(run_id)[-1]

    def add_artifact(
        self,
        artifact_id: str,
        run_id: str,
        artifact_type: str,
        path: str | None = None,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: str | None = None,
    ) -> ArtifactRecord:
        created = created_at or utc_now_iso()
        with closing(self.store.connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO artifacts (
                  artifact_id, run_id, type, path, content_type, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    run_id,
                    artifact_type,
                    path,
                    content_type,
                    _json_text(metadata) if metadata is not None else None,
                    created,
                ),
            )
            connection.commit()
        return self.list_artifacts(run_id)[-1]

    def add_tool_call(
        self,
        tool_call_id: str,
        run_id: str,
        tool_name: str,
        status: str,
        arguments: dict[str, Any],
        step_id: str | None = None,
        result: dict[str, Any] | None = None,
        error: Any | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> ToolCallRecord:
        started = started_at or utc_now_iso()
        with closing(self.store.connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO tool_calls (
                  tool_call_id, run_id, step_id, tool_name, status, arguments_json,
                  result_json, error_json, started_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tool_call_id,
                    run_id,
                    step_id,
                    tool_name,
                    status,
                    _json_text(arguments),
                    _json_text(result) if result is not None else None,
                    _json_text(error) if error is not None else None,
                    started,
                    completed_at,
                ),
            )
            connection.commit()
        return self.list_tool_calls(run_id)[-1]

    def add_hqs_report(
        self,
        hqs_id: str,
        run_id: str,
        scope: str,
        average_score: float,
        report: dict[str, Any],
        created_at: str | None = None,
    ) -> HQSReportRecord:
        created = created_at or utc_now_iso()
        with closing(self.store.connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO hqs_reports (
                  hqs_id, run_id, scope, average_score, report_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (hqs_id, run_id, scope, average_score, _json_text(report), created),
            )
            connection.commit()
        return self.list_hqs_reports(run_id)[-1]

    def add_workflow_checkpoint(
        self,
        checkpoint_id: str,
        run_id: str,
        workflow_id: str,
        state: dict[str, Any],
        step_name: str | None = None,
        created_at: str | None = None,
    ) -> WorkflowCheckpointRecord:
        created = created_at or utc_now_iso()
        with closing(self.store.connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO workflow_checkpoints (
                  checkpoint_id, run_id, workflow_id, step_name, state_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint_id,
                    run_id,
                    workflow_id,
                    step_name,
                    _json_text(state),
                    created,
                ),
            )
            connection.commit()
        return self.list_workflow_checkpoints(run_id)[-1]

    def list_runs(
        self,
        limit: int = 50,
        task_type: str | None = None,
        status: str | None = None,
    ) -> list[RunRecord]:
        clauses = []
        values: list[Any] = []
        if task_type:
            clauses.append("task_type = ?")
            values.append(task_type)
        if status:
            clauses.append("status = ?")
            values.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(max(1, min(limit, 500)))
        with closing(self.store.connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM runs
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                values,
            ).fetchall()
        return [_run_from_row(row) for row in rows]

    def get_run(self, run_id: str) -> RunRecord | None:
        with closing(self.store.connect()) as connection:
            row = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return _run_from_row(row) if row else None

    def list_run_steps(self, run_id: str) -> list[RunStepRecord]:
        with closing(self.store.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM run_steps WHERE run_id = ? ORDER BY started_at, step_id",
                (run_id,),
            ).fetchall()
        return [_step_from_row(row) for row in rows]

    def list_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        with closing(self.store.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM artifacts WHERE run_id = ? ORDER BY created_at, artifact_id",
                (run_id,),
            ).fetchall()
        return [_artifact_from_row(row) for row in rows]

    def list_tool_calls(self, run_id: str) -> list[ToolCallRecord]:
        with closing(self.store.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM tool_calls WHERE run_id = ? ORDER BY started_at, tool_call_id",
                (run_id,),
            ).fetchall()
        return [_tool_call_from_row(row) for row in rows]

    def list_hqs_reports(self, run_id: str) -> list[HQSReportRecord]:
        with closing(self.store.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM hqs_reports WHERE run_id = ? ORDER BY created_at, hqs_id",
                (run_id,),
            ).fetchall()
        return [_hqs_from_row(row) for row in rows]

    def list_workflow_checkpoints(self, run_id: str) -> list[WorkflowCheckpointRecord]:
        with closing(self.store.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM workflow_checkpoints WHERE run_id = ? ORDER BY created_at, checkpoint_id",
                (run_id,),
            ).fetchall()
        return [_workflow_checkpoint_from_row(row) for row in rows]


def _run_from_row(row: Any) -> RunRecord:
    return RunRecord(
        run_id=str(row["run_id"]),
        task_type=str(row["task_type"]),
        title=str(row["title"]),
        status=str(row["status"]),
        input=_json_value(row["input_json"], {}),
        output=_json_value(row["output_json"], None),
        trace_path=row["trace_path"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        completed_at=row["completed_at"],
    )


def _step_from_row(row: Any) -> RunStepRecord:
    return RunStepRecord(
        step_id=str(row["step_id"]),
        run_id=str(row["run_id"]),
        name=str(row["name"]),
        kind=str(row["kind"]),
        status=str(row["status"]),
        input=_json_value(row["input_json"], None),
        output=_json_value(row["output_json"], None),
        error=_json_value(row["error_json"], None),
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )


def _artifact_from_row(row: Any) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=str(row["artifact_id"]),
        run_id=str(row["run_id"]),
        type=str(row["type"]),
        path=row["path"],
        content_type=row["content_type"],
        metadata=_json_value(row["metadata_json"], None),
        created_at=str(row["created_at"]),
    )


def _tool_call_from_row(row: Any) -> ToolCallRecord:
    return ToolCallRecord(
        tool_call_id=str(row["tool_call_id"]),
        run_id=str(row["run_id"]),
        step_id=row["step_id"],
        tool_name=str(row["tool_name"]),
        status=str(row["status"]),
        arguments=_json_value(row["arguments_json"], {}),
        result=_json_value(row["result_json"], None),
        error=_json_value(row["error_json"], None),
        started_at=str(row["started_at"]),
        completed_at=row["completed_at"],
    )


def _hqs_from_row(row: Any) -> HQSReportRecord:
    return HQSReportRecord(
        hqs_id=str(row["hqs_id"]),
        run_id=str(row["run_id"]),
        scope=str(row["scope"]),
        average_score=float(row["average_score"]),
        report=_json_value(row["report_json"], {}),
        created_at=str(row["created_at"]),
    )


def _workflow_checkpoint_from_row(row: Any) -> WorkflowCheckpointRecord:
    return WorkflowCheckpointRecord(
        checkpoint_id=str(row["checkpoint_id"]),
        run_id=str(row["run_id"]),
        workflow_id=str(row["workflow_id"]),
        step_name=row["step_name"],
        state=_json_value(row["state_json"], {}),
        created_at=str(row["created_at"]),
    )


def _json_text(value: Any) -> str:
    return json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True)


def _json_value(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _json_safe(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _json_safe(value.to_dict())
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
