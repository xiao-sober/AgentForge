from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentforge.tasks.handlers.workflow_task import finalize_workflow_task_result
from agentforge.tasks.schemas import TaskRequest, TaskResult
from agentforge.workflows import WorkflowExecutionContext, WorkflowRunner, WorkflowStepResult


CODE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".yaml",
    ".yml",
    ".toml",
    ".css",
    ".html",
    ".sql",
}
EXCLUDED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
}
MAX_FILES = 12
MAX_BYTES_PER_FILE = 120_000


@dataclass(frozen=True)
class CodeSource:
    name: str
    kind: str
    content: str
    language: str | None = None
    path: Path | None = None

    def to_summary(self, root: Path) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "language": self.language,
            "path": _relative_or_absolute(self.path, root) if self.path else None,
            "line_count": len(self.content.splitlines()),
            "byte_count": len(self.content.encode("utf-8")),
        }


def handle_code_analysis_task(
    request: TaskRequest,
    project_root: Path,
    llm_client: Any | None = None,
) -> TaskResult:
    del llm_client
    runner = WorkflowRunner.for_task(
        project_root,
        workflow_id="code_analysis_workflow",
        task_type="code_analysis",
        steps=["resolve_sources", "analyze_sources", "build_report"],
    )
    runtime: dict[str, Any] = {}

    def resolve_sources(_: WorkflowExecutionContext) -> WorkflowStepResult:
        sources = _resolve_sources(request, project_root)
        source_summaries = [source.to_summary(project_root) for source in sources]
        runtime["sources"] = sources
        runtime["source_summaries"] = source_summaries
        return WorkflowStepResult(
            output={
                "source_count": len(sources),
                "sources": source_summaries,
            },
            state_updates={"source_summaries": source_summaries},
        )

    def analyze_sources(_: WorkflowExecutionContext) -> WorkflowStepResult:
        sources = runtime.get("sources")
        if not isinstance(sources, list):
            raise ValueError("Code sources were not resolved before analysis.")
        analysis = _analyze_sources(sources, project_root)
        runtime["analysis"] = analysis
        return WorkflowStepResult(
            output={
                "finding_count": analysis["summary"]["finding_count"],
                "high_count": analysis["summary"]["high_count"],
                "medium_count": analysis["summary"]["medium_count"],
                "line_count": analysis["summary"]["line_count"],
            },
            state_updates={"analysis_summary": analysis["summary"]},
        )

    def build_report(_: WorkflowExecutionContext) -> WorkflowStepResult:
        sources = runtime.get("sources")
        source_summaries = runtime.get("source_summaries")
        analysis = runtime.get("analysis")
        if not isinstance(sources, list) or not isinstance(source_summaries, list) or not isinstance(analysis, dict):
            raise ValueError("Code analysis workflow state is incomplete.")
        report = {
            "analysis": analysis,
            "sources": source_summaries,
        }
        artifacts = _source_artifacts(sources, project_root)
        runtime["report"] = report
        runtime["artifacts"] = artifacts
        return WorkflowStepResult(
            output={
                "status": "completed",
                "summary": analysis["summary"],
            },
            artifacts=artifacts,
            state_updates={"report": report, "artifacts": artifacts},
        )

    run_id = runner.execute(
        title="Code analysis",
        input_data=request.to_dict(),
        handlers={
            "resolve_sources": resolve_sources,
            "analyze_sources": analyze_sources,
            "build_report": build_report,
        },
    )
    return finalize_workflow_task_result(
        runner=runner,
        run_id=run_id,
        request=request,
        project_root=project_root,
        trace_type="code_analysis",
        success_state_key="report",
        failure_output_key="analysis",
    )


def _resolve_sources(request: TaskRequest, root: Path) -> list[CodeSource]:
    payload = request.payload()
    input_text = _optional_string(payload.get("input") or payload.get("code") or payload.get("text"))
    sources: list[CodeSource] = []
    sources.extend(_sources_from_payload_paths(payload, root))
    if input_text:
        sources.extend(_sources_from_code_fences(input_text))
        if not sources:
            path_sources = _sources_from_path_mentions(input_text, root)
            sources.extend(path_sources)
        if not sources:
            sources.append(
                CodeSource(
                    name="request",
                    kind="request_text",
                    content=input_text,
                    language=_optional_string(payload.get("language")),
                )
            )
    return sources[:MAX_FILES]


def _sources_from_payload_paths(payload: dict[str, Any], root: Path) -> list[CodeSource]:
    paths: list[str] = []
    for key in ["path", "file_path"]:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            paths.append(value.strip())
    for key in ["paths", "files"]:
        value = payload.get(key)
        if isinstance(value, list):
            paths.extend(item.strip() for item in value if isinstance(item, str) and item.strip())
    sources: list[CodeSource] = []
    for raw_path in paths[:MAX_FILES]:
        sources.extend(_read_code_sources(root, Path(raw_path)))
        if len(sources) >= MAX_FILES:
            break
    return sources[:MAX_FILES]


def _sources_from_code_fences(text: str) -> list[CodeSource]:
    sources: list[CodeSource] = []
    pattern = re.compile(r"```(?P<language>[A-Za-z0-9_+-]*)\s*(?P<code>.*?)```", re.DOTALL)
    for index, match in enumerate(pattern.finditer(text), start=1):
        code = match.group("code").strip("\n")
        if not code.strip():
            continue
        language = match.group("language").strip() or None
        sources.append(CodeSource(name=f"snippet_{index}", kind="code_fence", content=code, language=language))
        if len(sources) >= MAX_FILES:
            break
    return sources


def _sources_from_path_mentions(text: str, root: Path) -> list[CodeSource]:
    paths: list[str] = []
    pattern = re.compile(r"(?<!\w)([A-Za-z0-9_./\\-]+\.(?:py|ts|tsx|js|jsx|json|md|yaml|yml|toml|css|html|sql))(?!\w)")
    for match in pattern.finditer(text):
        value = match.group(1).strip(".,;:()[]{}\"'")
        if value and value not in paths:
            paths.append(value)
    sources: list[CodeSource] = []
    for raw_path in paths[:MAX_FILES]:
        try:
            sources.extend(_read_code_sources(root, Path(raw_path)))
        except ValueError:
            continue
        if len(sources) >= MAX_FILES:
            break
    return sources[:MAX_FILES]


def _read_code_sources(root: Path, path: Path) -> list[CodeSource]:
    resolved = _resolve_under_project(root, path)
    if resolved.is_dir():
        return _read_directory_sources(root, resolved)
    if not resolved.is_file():
        raise ValueError(f"Code path not found: {_relative_or_absolute(resolved, root)}")
    return [_read_file_source(root, resolved)]


def _read_directory_sources(root: Path, directory: Path) -> list[CodeSource]:
    sources: list[CodeSource] = []
    for path in sorted(directory.rglob("*")):
        if len(sources) >= MAX_FILES:
            break
        if not path.is_file() or _is_excluded(path, root) or path.suffix.lower() not in CODE_SUFFIXES:
            continue
        sources.append(_read_file_source(root, path))
    if not sources:
        raise ValueError(f"No supported code files found under {_relative_or_absolute(directory, root)}")
    return sources


def _read_file_source(root: Path, path: Path) -> CodeSource:
    if _is_excluded(path, root):
        raise ValueError(f"Code path is excluded from analysis: {_relative_or_absolute(path, root)}")
    if path.suffix.lower() not in CODE_SUFFIXES:
        raise ValueError(f"Unsupported code file suffix: {path.suffix}")
    byte_count = path.stat().st_size
    if byte_count > MAX_BYTES_PER_FILE:
        raise ValueError(f"Code file is too large for local analysis: {_relative_or_absolute(path, root)}")
    content = path.read_text(encoding="utf-8", errors="replace")
    return CodeSource(
        name=_relative_or_absolute(path, root),
        kind="file",
        content=content,
        language=_language_for_suffix(path.suffix),
        path=path,
    )


def _analyze_sources(sources: list[CodeSource], root: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    limitations: list[str] = []
    if not sources:
        limitations.append("No code source was supplied.")
    for source in sources:
        source_metrics = _source_metrics(source)
        metrics.append(source_metrics)
        findings.extend(_generic_findings(source))
        if _is_python_source(source):
            findings.extend(_python_findings(source))
        if _is_typescript_source(source):
            findings.extend(_typescript_findings(source))
        if source.kind == "request_text" and not _looks_like_code(source.content):
            findings.append(
                _finding(
                    "medium",
                    source.name,
                    None,
                    "missing_code_context",
                    "The request was classified as code analysis but no concrete code snippet or file path was provided.",
                    "Provide a code fence or a project-relative file path so the analyzer can inspect real code.",
                )
            )
            limitations.append("Only the natural-language request was available; code-level findings are limited.")
    summary = _analysis_summary(findings, metrics)
    return {
        "source_count": len(sources),
        "sources": [source.to_summary(root) for source in sources],
        "summary": summary,
        "metrics": metrics,
        "findings": findings,
        "limitations": limitations,
    }


def _source_metrics(source: CodeSource) -> dict[str, Any]:
    lines = source.content.splitlines()
    non_empty = [line for line in lines if line.strip()]
    comment_lines = [line for line in lines if line.strip().startswith(("#", "//", "/*", "*"))]
    return {
        "source": source.name,
        "kind": source.kind,
        "language": source.language,
        "line_count": len(lines),
        "non_empty_line_count": len(non_empty),
        "comment_line_count": len(comment_lines),
        "long_line_count": sum(1 for line in lines if len(line) > 120),
    }


def _generic_findings(source: CodeSource) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    lines = source.content.splitlines()
    for index, line in enumerate(lines, start=1):
        lowered = line.lower()
        if any(marker in lowered for marker in ["todo", "fixme", "hack"]):
            findings.append(
                _finding(
                    "low",
                    source.name,
                    index,
                    "unfinished_marker",
                    "The code contains TODO/FIXME/HACK markers.",
                    "Track or resolve unfinished implementation notes before relying on this path.",
                )
            )
        if re.search(r"\b(password|api[_-]?key|secret|token)\b\s*[:=]", lowered):
            findings.append(
                _finding(
                    "high",
                    source.name,
                    index,
                    "secret_keyword_assignment",
                    "A secret-like key appears near an assignment.",
                    "Move credentials to provider config or environment variables and avoid committing secrets.",
                )
            )
        if len(line) > 120:
            findings.append(
                _finding(
                    "low",
                    source.name,
                    index,
                    "long_line",
                    "Line length exceeds 120 characters.",
                    "Wrap the expression or split dense logic for readability.",
                )
            )
    if not source.content.strip():
        findings.append(
            _finding(
                "medium",
                source.name,
                None,
                "empty_source",
                "The source is empty.",
                "Provide code content before running analysis.",
            )
        )
    return findings[:40]


def _python_findings(source: CodeSource) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        tree = ast.parse(source.content)
    except SyntaxError as exc:
        return [
            _finding(
                "high",
                source.name,
                exc.lineno,
                "python_syntax_error",
                f"Python syntax error: {exc.msg}.",
                "Fix the syntax error before relying on static analysis or runtime behavior.",
            )
        ]

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and (
            node.type is None
            or (isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"})
        ):
            findings.append(
                _finding(
                    "medium",
                    source.name,
                    getattr(node, "lineno", None),
                    "broad_exception_handler",
                    "A broad exception handler can hide actionable failures.",
                    "Catch specific exception types and record enough context for recovery.",
                )
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
            findings.append(
                _finding(
                    "high",
                    source.name,
                    getattr(node, "lineno", None),
                    "python_eval_exec",
                    f"Use of {node.func.id} can execute untrusted code.",
                    "Replace dynamic execution with explicit parsing or a constrained dispatch table.",
                )
            )
        if isinstance(node, ast.Call) and _is_shell_true_call(node):
            findings.append(
                _finding(
                    "high",
                    source.name,
                    getattr(node, "lineno", None),
                    "subprocess_shell_true",
                    "subprocess call uses shell=True.",
                    "Pass argument lists directly and avoid shell=True unless the input is fully controlled.",
                )
            )
    function_count = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree))
    class_count = sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
    if function_count == 0 and class_count == 0 and len(source.content.splitlines()) > 80:
        findings.append(
            _finding(
                "low",
                source.name,
                None,
                "large_script_without_structure",
                "Large Python source has no functions or classes.",
                "Extract named functions so behavior is easier to test and reuse.",
            )
        )
    return findings


def _typescript_findings(source: CodeSource) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    lines = source.content.splitlines()
    for index, line in enumerate(lines, start=1):
        lowered = line.lower()
        if "@ts-ignore" in lowered:
            findings.append(
                _finding(
                    "medium",
                    source.name,
                    index,
                    "ts_ignore",
                    "TypeScript error suppression is present.",
                    "Prefer fixing the type boundary or using a narrow typed adapter.",
                )
            )
        if "dangerouslysetinnerhtml" in lowered:
            findings.append(
                _finding(
                    "high",
                    source.name,
                    index,
                    "dangerous_inner_html",
                    "React dangerouslySetInnerHTML is present.",
                    "Sanitize input and isolate this rendering path behind a reviewed component.",
                )
            )
        if re.search(r":\s*any\b", line):
            findings.append(
                _finding(
                    "low",
                    source.name,
                    index,
                    "typescript_any",
                    "Explicit `any` weakens local type guarantees.",
                    "Replace `any` with a focused interface or unknown plus validation.",
                )
            )
    return findings


def _analysis_summary(findings: list[dict[str, Any]], metrics: list[dict[str, Any]]) -> dict[str, Any]:
    severities = [str(finding.get("severity") or "info") for finding in findings]
    return {
        "finding_count": len(findings),
        "high_count": severities.count("high"),
        "medium_count": severities.count("medium"),
        "low_count": severities.count("low"),
        "info_count": severities.count("info"),
        "line_count": sum(int(metric.get("line_count") or 0) for metric in metrics),
        "source_count": len(metrics),
        "languages": sorted(
            {
                str(metric.get("language"))
                for metric in metrics
                if isinstance(metric.get("language"), str) and metric.get("language")
            }
        ),
    }


def _source_artifacts(sources: list[CodeSource], root: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for source in sources:
        if source.path:
            artifacts.append({"type": "code_source", "path": _relative_or_absolute(source.path, root)})
        else:
            artifacts.append({"type": source.kind, "path": source.name})
    return artifacts


def _resolve_under_project(root: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("Code analysis paths must stay under the project root.")
    return resolved


def _is_excluded(path: Path, root: Path) -> bool:
    try:
        relative_parts = path.resolve().relative_to(root).parts
    except ValueError:
        return True
    return any(part in EXCLUDED_DIR_NAMES for part in relative_parts)


def _is_python_source(source: CodeSource) -> bool:
    return (source.language or "").lower() in {"python", "py"} or (source.path is not None and source.path.suffix == ".py")


def _is_typescript_source(source: CodeSource) -> bool:
    language = (source.language or "").lower()
    return language in {"typescript", "ts", "tsx", "javascript", "js", "jsx"} or (
        source.path is not None and source.path.suffix.lower() in {".ts", ".tsx", ".js", ".jsx"}
    )


def _is_shell_true_call(node: ast.Call) -> bool:
    return any(keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True for keyword in node.keywords)


def _looks_like_code(value: str) -> bool:
    return bool(re.search(r"\b(def|class|function|const|let|var|import|from|return|if|for|while)\b|[{};=()]", value))


def _language_for_suffix(suffix: str) -> str | None:
    return {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".js": "javascript",
        ".jsx": "jsx",
        ".json": "json",
        ".md": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".css": "css",
        ".html": "html",
        ".sql": "sql",
    }.get(suffix.lower())


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
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)
