from __future__ import annotations

from pathlib import Path

MAX_REQUEST_BODY_BYTES = 1_000_000


def default_frontend_dist(project_root: Path | str = ".") -> Path:
    return Path(project_root).resolve() / "apps" / "web" / "frontend" / "dist"
