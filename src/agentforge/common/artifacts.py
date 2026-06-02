from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CleanupResult:
    dry_run: bool
    removed: list[str]
    kept: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "removed": self.removed,
            "kept": self.kept,
            "removed_count": len(self.removed),
            "kept_count": len(self.kept),
        }


def cleanup_artifacts(
    project_root: Path | str = ".",
    max_traces: int = 200,
    max_runs_per_skill_version: int = 20,
    dry_run: bool = True,
) -> CleanupResult:
    if max_traces < 0:
        raise ValueError("max_traces must be >= 0.")
    if max_runs_per_skill_version < 0:
        raise ValueError("max_runs_per_skill_version must be >= 0.")

    root = Path(project_root).resolve()
    removed: list[str] = []
    kept: list[str] = []

    _collect_trace_cleanup(root, max_traces, dry_run, removed, kept)
    _collect_run_cleanup(root, max_runs_per_skill_version, dry_run, removed, kept)
    return CleanupResult(dry_run=dry_run, removed=removed, kept=kept)


def _collect_trace_cleanup(root: Path, max_traces: int, dry_run: bool, removed: list[str], kept: list[str]) -> None:
    traces_dir = root / "traces"
    traces = sorted(traces_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True) if traces_dir.exists() else []
    for index, path in enumerate(traces):
        relative = _relative_or_absolute(path, root)
        if index < max_traces:
            kept.append(relative)
            continue
        _remove_file(path, root, dry_run)
        removed.append(relative)


def _collect_run_cleanup(root: Path, max_runs: int, dry_run: bool, removed: list[str], kept: list[str]) -> None:
    runs_root = root / "runs"
    if not runs_root.exists():
        return
    for version_dir in runs_root.glob("*/*"):
        if not version_dir.is_dir():
            continue
        run_dirs = sorted(
            [path for path in version_dir.iterdir() if path.is_dir()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for index, path in enumerate(run_dirs):
            relative = _relative_or_absolute(path, root)
            if index < max_runs:
                kept.append(relative)
                continue
            _remove_directory(path, root, dry_run)
            removed.append(relative)


def _remove_file(path: Path, root: Path, dry_run: bool) -> None:
    _assert_inside(root, path)
    if not dry_run:
        path.unlink()


def _remove_directory(path: Path, root: Path, dry_run: bool) -> None:
    _assert_inside(root, path)
    if not dry_run:
        shutil.rmtree(path)


def _assert_inside(root: Path, path: Path) -> None:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path == resolved_root or resolved_root not in resolved_path.parents:
        raise ValueError(f"Refusing to clean path outside project root: {path}")


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
