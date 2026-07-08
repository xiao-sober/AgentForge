from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from agentforge.tasks.handlers.workflow_task import finalize_workflow_task_result
from agentforge.tasks.schemas import TaskRequest, TaskResult
from agentforge.workflows import WorkflowExecutionContext, WorkflowRunner, WorkflowStepResult


DATA_SUFFIXES = {".csv", ".tsv", ".json", ".jsonl", ".ndjson"}
EXCLUDED_DIR_NAMES = {".git", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "__pycache__", "dist", "node_modules"}
MAX_SOURCES = 8
MAX_BYTES_PER_FILE = 160_000
MAX_ROWS = 1_000


@dataclass(frozen=True)
class DataSource:
    name: str
    kind: str
    content: str
    format: str | None = None
    path: Path | None = None

    def to_summary(self, root: Path) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "format": self.format,
            "path": _relative_or_absolute(self.path, root) if self.path else None,
            "line_count": len(self.content.splitlines()),
            "byte_count": len(self.content.encode("utf-8")),
        }


def handle_data_analysis_task(
    request: TaskRequest,
    project_root: Path,
    llm_client: Any | None = None,
) -> TaskResult:
    del llm_client
    runner = WorkflowRunner.for_task(
        project_root,
        workflow_id="data_analysis_workflow",
        task_type="data_analysis",
        steps=["resolve_data", "profile_data", "build_report"],
    )
    runtime: dict[str, Any] = {}

    def resolve_data(_: WorkflowExecutionContext) -> WorkflowStepResult:
        sources = _resolve_sources(request, project_root)
        source_summaries = [source.to_summary(project_root) for source in sources]
        runtime["sources"] = sources
        runtime["source_summaries"] = source_summaries
        return WorkflowStepResult(
            output={"source_count": len(sources), "sources": source_summaries},
            state_updates={"source_summaries": source_summaries},
        )

    def profile_data(_: WorkflowExecutionContext) -> WorkflowStepResult:
        sources = runtime.get("sources")
        if not isinstance(sources, list):
            raise ValueError("Data sources were not resolved before profiling.")
        analysis = _profile_sources(sources, project_root)
        runtime["analysis"] = analysis
        return WorkflowStepResult(
            output={
                "source_count": analysis["summary"]["source_count"],
                "row_count": analysis["summary"]["row_count"],
                "column_count": analysis["summary"]["column_count"],
                "finding_count": analysis["summary"]["finding_count"],
            },
            state_updates={"analysis_summary": analysis["summary"]},
        )

    def build_report(_: WorkflowExecutionContext) -> WorkflowStepResult:
        sources = runtime.get("sources")
        source_summaries = runtime.get("source_summaries")
        analysis = runtime.get("analysis")
        if not isinstance(sources, list) or not isinstance(source_summaries, list) or not isinstance(analysis, dict):
            raise ValueError("Data analysis workflow state is incomplete.")
        report = {"analysis": analysis, "sources": source_summaries}
        artifacts = _source_artifacts(sources, project_root)
        runtime["report"] = report
        runtime["artifacts"] = artifacts
        return WorkflowStepResult(
            output={"status": "completed", "summary": analysis["summary"]},
            artifacts=artifacts,
            state_updates={"report": report, "artifacts": artifacts},
        )

    run_id = runner.execute(
        title="Data analysis",
        input_data=request.to_dict(),
        handlers={
            "resolve_data": resolve_data,
            "profile_data": profile_data,
            "build_report": build_report,
        },
    )
    return finalize_workflow_task_result(
        runner=runner,
        run_id=run_id,
        request=request,
        project_root=project_root,
        trace_type="data_analysis",
        success_state_key="report",
        failure_output_key="analysis",
    )


def _resolve_sources(request: TaskRequest, root: Path) -> list[DataSource]:
    payload = request.payload()
    sources = _sources_from_payload_paths(payload, root)
    input_text = _optional_string(payload.get("input") or payload.get("data") or payload.get("text"))
    explicit_format = _optional_string(payload.get("format"))
    if input_text:
        if not sources:
            sources.extend(_sources_from_data_fences(input_text, explicit_format))
        if not sources:
            sources.extend(_sources_from_path_mentions(input_text, root))
        if not sources:
            sources.append(
                DataSource(
                    name="request",
                    kind="inline",
                    content=_strip_data_fence(input_text),
                    format=explicit_format or _guess_format_from_content(input_text),
                )
            )
    if not sources:
        raise ValueError("data_analysis requires input.data, input.input, input.path, input.file_path, input.paths, or input.files.")
    return sources[:MAX_SOURCES]


def _sources_from_data_fences(text: str, explicit_format: str | None = None) -> list[DataSource]:
    sources: list[DataSource] = []
    pattern = re.compile(r"```(?P<format>[A-Za-z0-9_+-]*)\s*(?P<data>.*?)```", re.DOTALL)
    for index, match in enumerate(pattern.finditer(text), start=1):
        content = match.group("data").strip("\n")
        if not content.strip():
            continue
        fence_format = _normalize_format(match.group("format"))
        sources.append(
            DataSource(
                name=f"dataset_{index}",
                kind="data_fence",
                content=content,
                format=explicit_format or fence_format or _guess_format_from_content(content),
            )
        )
        if len(sources) >= MAX_SOURCES:
            break
    return sources


def _sources_from_payload_paths(payload: dict[str, Any], root: Path) -> list[DataSource]:
    paths: list[str] = []
    for key in ["path", "file_path"]:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            paths.append(value.strip())
    for key in ["paths", "files"]:
        value = payload.get(key)
        if isinstance(value, list):
            paths.extend(item.strip() for item in value if isinstance(item, str) and item.strip())

    sources: list[DataSource] = []
    for raw_path in paths[:MAX_SOURCES]:
        path = _resolve_under_project(root, Path(raw_path))
        if path.is_dir():
            sources.extend(_read_directory_sources(root, path))
        else:
            sources.append(_read_data_source(root, path))
        if len(sources) >= MAX_SOURCES:
            break
    return sources[:MAX_SOURCES]


def _sources_from_path_mentions(text: str, root: Path) -> list[DataSource]:
    sources: list[DataSource] = []
    seen: set[str] = set()
    for match in _PATH_PATTERN.finditer(text):
        raw_path = match.group(1).strip(".,;:()[]{}\"'")
        if not raw_path or raw_path in seen:
            continue
        seen.add(raw_path)
        path = (root / raw_path).resolve()
        if path.exists():
            sources.append(_read_data_source(root, path))
        if len(sources) >= MAX_SOURCES:
            break
    return sources


_PATH_PATTERN = re.compile(r"(?<!\w)([A-Za-z0-9_./\\-]+\.(?:csv|tsv|json|jsonl|ndjson))(?!\w)")


def _read_directory_sources(root: Path, directory: Path) -> list[DataSource]:
    sources: list[DataSource] = []
    for path in sorted(directory.rglob("*")):
        if len(sources) >= MAX_SOURCES:
            break
        if path.is_file() and path.suffix.lower() in DATA_SUFFIXES and not _is_excluded(path, root):
            sources.append(_read_data_source(root, path))
    return sources


def _read_data_source(root: Path, path: Path) -> DataSource:
    resolved = _resolve_under_project(root, path)
    if resolved.suffix.lower() not in DATA_SUFFIXES:
        raise ValueError(f"Unsupported data type for local analysis: {resolved.suffix or resolved.name}")
    if resolved.stat().st_size > MAX_BYTES_PER_FILE:
        raise ValueError(f"Data file is too large for local analysis: {_relative_or_absolute(resolved, root)}")
    content = resolved.read_text(encoding="utf-8", errors="replace")
    return DataSource(
        name=resolved.name,
        kind="file",
        path=resolved,
        content=content,
        format=_format_from_suffix(resolved.suffix),
    )


def _profile_sources(sources: list[DataSource], root: Path) -> dict[str, Any]:
    tables: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    limitations: list[str] = []
    for source in sources:
        source_name = _relative_or_absolute(source.path, root) if source.path else source.name
        try:
            rows, columns, detected_format = _parse_source(source)
        except ValueError as exc:
            rows, columns, detected_format = [], [], source.format or "unknown"
            findings.append(_finding("high", source_name, None, "parse_error", str(exc), "Provide valid CSV, TSV, JSON array/object, or JSONL input."))

        row_count = len(rows)
        if row_count > MAX_ROWS:
            limitations.append(f"{source_name} was sampled to the first {MAX_ROWS} rows.")
            rows = rows[:MAX_ROWS]
            row_count = len(rows)
        profile = _table_profile(source_name, detected_format, rows, columns)
        tables.append(profile)
        findings.extend(_table_findings(profile))
        if source.kind == "inline" and detected_format == "unknown":
            limitations.append("Only unstructured request text was available; data profiling is limited.")

    summary = _summary(tables, findings, len(sources))
    if not findings:
        findings.append(_finding("info", "data", None, "no_obvious_data_quality_risks", "No obvious local data quality issues were detected.", "Validate business rules and semantics manually."))
        summary = _summary(tables, findings, len(sources))

    return {
        "summary": summary,
        "tables": tables,
        "findings": findings,
        "limitations": limitations,
    }


def _parse_source(source: DataSource) -> tuple[list[dict[str, Any]], list[str], str]:
    fmt = source.format or _guess_format_from_content(source.content)
    content = source.content.strip()
    if not content:
        return [], [], fmt or "unknown"
    if fmt in {"csv", "tsv"}:
        return _parse_delimited(content, "\t" if fmt == "tsv" else ","), _columns_from_delimited(content, "\t" if fmt == "tsv" else ","), fmt
    if fmt == "jsonl":
        rows = []
        for line in content.splitlines():
            if line.strip():
                item = json.loads(line)
                rows.append(item if isinstance(item, dict) else {"value": item})
        return rows, _columns_from_rows(rows), fmt
    if fmt == "json":
        parsed = json.loads(content)
        rows = _rows_from_json(parsed)
        return rows, _columns_from_rows(rows), fmt
    raise ValueError("Could not detect a supported data format.")


def _parse_delimited(content: str, delimiter: str) -> list[dict[str, Any]]:
    sample = io.StringIO(content)
    reader = csv.DictReader(sample, delimiter=delimiter)
    if reader.fieldnames:
        return [dict(row) for row in reader]
    sample.seek(0)
    raw_rows = list(csv.reader(sample, delimiter=delimiter))
    if not raw_rows:
        return []
    width = max(len(row) for row in raw_rows)
    columns = [f"column_{index}" for index in range(1, width + 1)]
    return [{columns[index]: row[index] if index < len(row) else "" for index in range(width)} for row in raw_rows]


def _columns_from_delimited(content: str, delimiter: str) -> list[str]:
    sample = io.StringIO(content)
    reader = csv.reader(sample, delimiter=delimiter)
    try:
        first = next(reader)
    except StopIteration:
        return []
    return [str(value).strip() or f"column_{index}" for index, value in enumerate(first, start=1)]


def _rows_from_json(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item if isinstance(item, dict) else {"value": item} for item in value]
    if isinstance(value, dict):
        list_values = [item for item in value.values() if isinstance(item, list)]
        if len(list_values) == 1:
            return _rows_from_json(list_values[0])
        return [value]
    return [{"value": value}]


def _columns_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(str(key))
    return columns


def _table_profile(name: str, fmt: str, rows: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    missing_by_column: dict[str, int] = {}
    numeric_stats: dict[str, dict[str, float]] = {}
    for column in columns:
        values = [row.get(column) for row in rows]
        missing_by_column[column] = sum(1 for value in values if _is_missing(value))
        numeric_values = [_to_float(value) for value in values if _to_float(value) is not None]
        if numeric_values:
            numeric_stats[column] = {
                "min": min(numeric_values),
                "max": max(numeric_values),
                "mean": mean(numeric_values),
            }
    return {
        "name": name,
        "format": fmt,
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": columns,
        "missing_by_column": missing_by_column,
        "missing_value_count": sum(missing_by_column.values()),
        "numeric_stats": numeric_stats,
        "sample_rows": rows[:5],
    }


def _table_findings(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    name = str(profile.get("name") or "data")
    row_count = int(profile.get("row_count") or 0)
    column_count = int(profile.get("column_count") or 0)
    missing_count = int(profile.get("missing_value_count") or 0)
    if row_count == 0:
        findings.append(_finding("high", name, None, "empty_dataset", "Dataset has no rows.", "Provide rows before using this dataset for analysis."))
    if column_count == 0:
        findings.append(_finding("high", name, None, "missing_columns", "Dataset has no detected columns.", "Provide structured CSV, JSON object rows, or JSONL records."))
    if missing_count:
        findings.append(_finding("low", name, None, "missing_values", f"Dataset has {missing_count} missing values.", "Review missing values before downstream use."))
    columns = [str(column) for column in profile.get("columns", []) if isinstance(column, str)]
    if len(columns) != len(set(columns)):
        findings.append(_finding("medium", name, None, "duplicate_columns", "Dataset has duplicate column names.", "Rename duplicate columns to avoid ambiguous processing."))
    return findings


def _summary(tables: list[dict[str, Any]], findings: list[dict[str, Any]], source_count: int) -> dict[str, Any]:
    severities = [str(finding.get("severity") or "info") for finding in findings]
    all_columns: set[str] = set()
    for table in tables:
        all_columns.update(str(column) for column in table.get("columns", []) if isinstance(column, str))
    return {
        "source_count": source_count,
        "table_count": len(tables),
        "row_count": sum(int(table.get("row_count") or 0) for table in tables),
        "column_count": len(all_columns),
        "missing_value_count": sum(int(table.get("missing_value_count") or 0) for table in tables),
        "numeric_column_count": sum(len(table.get("numeric_stats") or {}) for table in tables),
        "finding_count": len(findings),
        "high_count": severities.count("high"),
        "medium_count": severities.count("medium"),
        "low_count": severities.count("low"),
        "info_count": severities.count("info"),
    }


def _strip_data_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _guess_format_from_content(text: str) -> str | None:
    stripped = _strip_data_fence(text).strip()
    if not stripped:
        return None
    if stripped.startswith("{") or stripped.startswith("["):
        return "json"
    lines = [line for line in stripped.splitlines() if line.strip()]
    if len(lines) >= 2 and all(line.lstrip().startswith(("{", "[")) for line in lines):
        return "jsonl"
    if lines and "\t" in lines[0]:
        return "tsv"
    if lines and "," in lines[0]:
        return "csv"
    return None


def _format_from_suffix(suffix: str) -> str:
    normalized = suffix.lower()
    if normalized == ".tsv":
        return "tsv"
    if normalized in {".jsonl", ".ndjson"}:
        return "jsonl"
    if normalized == ".json":
        return "json"
    return "csv"


def _normalize_format(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    if normalized in {"csv", "tsv", "json", "jsonl", "ndjson"}:
        return "jsonl" if normalized == "ndjson" else normalized
    return None


def _source_artifacts(sources: list[DataSource], root: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for source in sources:
        if source.path:
            artifacts.append({"type": "data", "path": _relative_or_absolute(source.path, root)})
    return artifacts


def _resolve_under_project(root: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("Data path must stay under the project root.")
    if _is_excluded(resolved, root):
        raise ValueError("Data path points to an excluded directory.")
    if not resolved.exists():
        raise ValueError(f"Data path not found: {_relative_or_absolute(resolved, root)}")
    return resolved


def _is_excluded(path: Path, root: Path) -> bool:
    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        relative_parts = path.parts
    return any(part in EXCLUDED_DIR_NAMES for part in relative_parts)


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _finding(
    severity: str,
    source: str,
    line: int | None,
    rule: str,
    message: str,
    recommendation: str,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "source": source,
        "line": line,
        "rule": rule,
        "message": message,
        "recommendation": recommendation,
    }


def _optional_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _relative_or_absolute(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
