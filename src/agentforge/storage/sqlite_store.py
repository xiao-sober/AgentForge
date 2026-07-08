from __future__ import annotations

import sqlite3
from pathlib import Path

from agentforge.storage.migrations import initialize_database


class SQLiteStore:
    """Small sqlite3-backed storage helper for local AgentForge indexes."""

    def __init__(self, project_root: Path | str = ".", db_path: Path | str | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.db_path = self._resolve_db_path(db_path)

    def initialize(self) -> Path:
        return initialize_database(self.db_path)

    def connect(self) -> sqlite3.Connection:
        self.initialize()
        try:
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            return connection
        except sqlite3.DatabaseError as exc:
            raise RuntimeError(f"SQLite database open failed for {self.db_path}: {exc}") from exc

    def _resolve_db_path(self, db_path: Path | str | None) -> Path:
        if db_path is None:
            return self.project_root / "data" / "agentforge.db"
        candidate = Path(db_path)
        resolved = candidate if candidate.is_absolute() else self.project_root / candidate
        resolved = resolved.resolve()
        if not _is_inside(self.project_root, resolved):
            raise ValueError("SQLite database path must stay under the project root.")
        return resolved


def _is_inside(root: Path, path: Path) -> bool:
    root = root.resolve()
    path = path.resolve()
    return path == root or root in path.parents
