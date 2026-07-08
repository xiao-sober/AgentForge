from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentforge.tasks.handlers.workflow_task import finalize_workflow_task_result
from agentforge.tasks.schemas import TaskRequest, TaskResult
from agentforge.workflows import WorkflowExecutionContext, WorkflowRunner, WorkflowStepResult


DOCUMENT_SUFFIXES = {".md", ".markdown", ".txt", ".rst", ".adoc", ".html", ".htm"}
EXCLUDED_DIR_NAMES = {".git", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "__pycache__", "dist", "node_modules"}
MAX_DOCUMENTS = 10
MAX_BYTES_PER_FILE = 160_000


@dataclass(frozen=True)
class DocumentSource:
    name: str
    kind: str
    content: str
    path: Path | None = None

    def to_summary(self, root: Path) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "path": _relative_or_absolute(self.path, root) if self.path else None,
            "line_count": len(self.content.splitlines()),
            "word_count": _word_count(self.content),
            "byte_count": len(self.content.encode("utf-8")),
        }


def handle_document_analysis_task(
    request: TaskRequest,
    project_root: Path,
    llm_client: Any | None = None,
) -> TaskResult:
    del llm_client
    runner = WorkflowRunner.for_task(
        project_root,
        workflow_id="document_analysis_workflow",
        task_type="document_analysis",
        steps=["resolve_documents", "analyze_documents", "build_report"],
    )
    runtime: dict[str, Any] = {}

    def resolve_documents(_: WorkflowExecutionContext) -> WorkflowStepResult:
        documents = _resolve_documents(request, project_root)
        source_summaries = [source.to_summary(project_root) for source in documents]
        runtime["documents"] = documents
        runtime["source_summaries"] = source_summaries
        return WorkflowStepResult(
            output={"document_count": len(documents), "documents": source_summaries},
            state_updates={"document_summaries": source_summaries},
        )

    def analyze_documents(_: WorkflowExecutionContext) -> WorkflowStepResult:
        documents = runtime.get("documents")
        if not isinstance(documents, list):
            raise ValueError("Documents were not resolved before analysis.")
        analysis = _analyze_documents(documents, project_root)
        runtime["analysis"] = analysis
        return WorkflowStepResult(
            output={
                "document_count": analysis["summary"]["document_count"],
                "word_count": analysis["summary"]["word_count"],
                "finding_count": analysis["summary"]["finding_count"],
            },
            state_updates={"analysis_summary": analysis["summary"]},
        )

    def build_report(_: WorkflowExecutionContext) -> WorkflowStepResult:
        documents = runtime.get("documents")
        source_summaries = runtime.get("source_summaries")
        analysis = runtime.get("analysis")
        if not isinstance(documents, list) or not isinstance(source_summaries, list) or not isinstance(analysis, dict):
            raise ValueError("Document analysis workflow state is incomplete.")
        report = {"analysis": analysis, "documents": source_summaries}
        artifacts = _document_artifacts(documents, project_root)
        runtime["report"] = report
        runtime["artifacts"] = artifacts
        return WorkflowStepResult(
            output={"status": "completed", "summary": analysis["summary"]},
            artifacts=artifacts,
            state_updates={"report": report, "artifacts": artifacts},
        )

    run_id = runner.execute(
        title="Document analysis",
        input_data=request.to_dict(),
        handlers={
            "resolve_documents": resolve_documents,
            "analyze_documents": analyze_documents,
            "build_report": build_report,
        },
    )
    return finalize_workflow_task_result(
        runner=runner,
        run_id=run_id,
        request=request,
        project_root=project_root,
        trace_type="document_analysis",
        success_state_key="report",
        failure_output_key="analysis",
    )


def _resolve_documents(request: TaskRequest, root: Path) -> list[DocumentSource]:
    payload = request.payload()
    sources = _sources_from_payload_paths(payload, root)
    input_text = _optional_string(payload.get("input") or payload.get("text") or payload.get("content"))
    if input_text:
        if not sources:
            sources.extend(_sources_from_path_mentions(input_text, root))
        if not sources:
            sources.append(DocumentSource(name="request", kind="request_text", content=input_text))
    if not sources:
        raise ValueError("document_analysis requires input.text, input.input, input.path, input.file_path, input.paths, or input.files.")
    return sources[:MAX_DOCUMENTS]


def _sources_from_payload_paths(payload: dict[str, Any], root: Path) -> list[DocumentSource]:
    paths: list[str] = []
    for key in ["path", "file_path"]:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            paths.append(value.strip())
    for key in ["paths", "files"]:
        value = payload.get(key)
        if isinstance(value, list):
            paths.extend(item.strip() for item in value if isinstance(item, str) and item.strip())

    sources: list[DocumentSource] = []
    for raw_path in paths[:MAX_DOCUMENTS]:
        path = _resolve_under_project(root, Path(raw_path))
        if path.is_dir():
            sources.extend(_read_directory_documents(root, path))
        else:
            sources.append(_read_document_source(root, path))
        if len(sources) >= MAX_DOCUMENTS:
            break
    return sources[:MAX_DOCUMENTS]


def _sources_from_path_mentions(text: str, root: Path) -> list[DocumentSource]:
    pattern = re.compile(r"(?<!\w)([A-Za-z0-9_./\\-]+\.(?:md|markdown|txt|rst|adoc|html|htm))(?!\w)")
    sources: list[DocumentSource] = []
    seen: set[str] = set()
    for match in pattern.finditer(text):
        raw_path = match.group(1).strip(".,;:()[]{}\"'")
        if not raw_path or raw_path in seen:
            continue
        seen.add(raw_path)
        path = (root / raw_path).resolve()
        if path.exists():
            sources.append(_read_document_source(root, path))
        if len(sources) >= MAX_DOCUMENTS:
            break
    return sources


def _read_directory_documents(root: Path, directory: Path) -> list[DocumentSource]:
    sources: list[DocumentSource] = []
    for path in sorted(directory.rglob("*")):
        if len(sources) >= MAX_DOCUMENTS:
            break
        if path.is_file() and path.suffix.lower() in DOCUMENT_SUFFIXES and not _is_excluded(path, root):
            sources.append(_read_document_source(root, path))
    return sources


def _read_document_source(root: Path, path: Path) -> DocumentSource:
    resolved = _resolve_under_project(root, path)
    if resolved.suffix.lower() not in DOCUMENT_SUFFIXES:
        raise ValueError(f"Unsupported document type for local analysis: {resolved.suffix or resolved.name}")
    if resolved.stat().st_size > MAX_BYTES_PER_FILE:
        raise ValueError(f"Document is too large for local analysis: {_relative_or_absolute(resolved, root)}")
    content = resolved.read_text(encoding="utf-8", errors="replace")
    return DocumentSource(
        name=resolved.name,
        kind="file",
        path=resolved,
        content=content,
    )


def _analyze_documents(documents: list[DocumentSource], root: Path) -> dict[str, Any]:
    document_reports: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    limitations: list[str] = []

    for source in documents:
        headings = _headings(source.content)
        links = re.findall(r"\[[^\]]+\]\([^)]+\)|https?://\S+", source.content)
        code_blocks = len(re.findall(r"```", source.content)) // 2
        long_lines = [index for index, line in enumerate(source.content.splitlines(), start=1) if len(line) > 160]
        title = headings[0]["text"] if headings else _first_non_empty_line(source.content)
        source_name = _relative_or_absolute(source.path, root) if source.path else source.name
        report = {
            "name": source.name,
            "path": _relative_or_absolute(source.path, root) if source.path else None,
            "kind": source.kind,
            "title": title,
            "heading_count": len(headings),
            "headings": headings[:20],
            "link_count": len(links),
            "code_block_count": code_blocks,
            "line_count": len(source.content.splitlines()),
            "word_count": _word_count(source.content),
            "char_count": len(source.content),
        }
        document_reports.append(report)

        if not source.content.strip():
            findings.append(_finding("high", source_name, None, "empty_document", "Document has no readable content.", "Provide document text or a supported UTF-8 text file."))
        if source.kind == "request_text":
            limitations.append("Only request text was available; document-level structure may be incomplete.")
        if not headings and _word_count(source.content) >= 80:
            findings.append(_finding("low", source_name, None, "missing_headings", "Long document has no detected headings.", "Add headings so readers can scan the document structure."))
        if long_lines:
            findings.append(_finding("low", source_name, long_lines[0], "long_line", "Document contains very long lines.", "Wrap long prose or split dense content into shorter paragraphs."))
        if re.search(r"\b(TODO|FIXME|TBD)\b", source.content, flags=re.IGNORECASE):
            findings.append(_finding("medium", source_name, None, "placeholder_text", "Document contains placeholder markers.", "Resolve TODO/FIXME/TBD markers before treating the document as final."))

    summary = _summary(document_reports, findings)
    if not findings:
        findings.append(_finding("info", "documents", None, "no_obvious_document_risks", "No obvious local document quality issues were detected.", "Review manually for domain-specific accuracy."))
        summary = _summary(document_reports, findings)

    return {
        "summary": summary,
        "documents": document_reports,
        "findings": findings,
        "limitations": limitations,
    }


def _summary(document_reports: list[dict[str, Any]], findings: list[dict[str, Any]]) -> dict[str, Any]:
    severities = [str(finding.get("severity") or "info") for finding in findings]
    return {
        "document_count": len(document_reports),
        "line_count": sum(int(report.get("line_count") or 0) for report in document_reports),
        "word_count": sum(int(report.get("word_count") or 0) for report in document_reports),
        "heading_count": sum(int(report.get("heading_count") or 0) for report in document_reports),
        "link_count": sum(int(report.get("link_count") or 0) for report in document_reports),
        "code_block_count": sum(int(report.get("code_block_count") or 0) for report in document_reports),
        "finding_count": len(findings),
        "high_count": severities.count("high"),
        "medium_count": severities.count("medium"),
        "low_count": severities.count("low"),
        "info_count": severities.count("info"),
    }


def _headings(text: str) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            headings.append({"level": len(match.group(1)), "text": match.group(2).strip(), "line": index})
    return headings


def _first_non_empty_line(text: str) -> str | None:
    for line in text.splitlines():
        value = line.strip()
        if value:
            return value[:120]
    return None


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def _document_artifacts(documents: list[DocumentSource], root: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for source in documents:
        if source.path:
            artifacts.append({"type": "document", "path": _relative_or_absolute(source.path, root)})
    return artifacts


def _resolve_under_project(root: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("Document path must stay under the project root.")
    if _is_excluded(resolved, root):
        raise ValueError("Document path points to an excluded directory.")
    if not resolved.exists():
        raise ValueError(f"Document path not found: {_relative_or_absolute(resolved, root)}")
    return resolved


def _is_excluded(path: Path, root: Path) -> bool:
    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        relative_parts = path.parts
    return any(part in EXCLUDED_DIR_NAMES for part in relative_parts)


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
