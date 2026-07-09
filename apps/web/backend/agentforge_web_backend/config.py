from __future__ import annotations

from pathlib import Path

MAX_REQUEST_BODY_BYTES = 1_000_000
MAX_UPLOAD_BODY_BYTES = 30_000_000
MAX_UPLOAD_FILE_BYTES = 10_000_000
MAX_UPLOAD_FILES = 8


def default_frontend_dist(project_root: Path | str = ".") -> Path:
    return Path(project_root).resolve() / "apps" / "web" / "frontend" / "dist"
