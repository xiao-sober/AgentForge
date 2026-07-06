from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse, HTMLResponse, Response

FRONTEND_NOT_BUILT_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>AgentForge Web frontend is not built</title>
  </head>
  <body>
    <h1>AgentForge Web frontend is not built.</h1>
    <p>Run <code>npm install</code> and <code>npm run build</code> in <code>apps/web/frontend</code>.</p>
  </body>
</html>
"""


def frontend_response(path: str, dist: Path) -> Response:
    dist = dist.resolve()
    index = dist / "index.html"
    if not index.is_file():
        return HTMLResponse(FRONTEND_NOT_BUILT_HTML, status_code=503)

    requested = (dist / path).resolve() if path else index
    if requested.is_file() and _is_under(requested, dist):
        return FileResponse(requested)
    if not _is_under(requested, dist) or Path(path).suffix:
        return HTMLResponse("Not found.", status_code=404)
    return FileResponse(index)


def _is_under(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    resolved_root = root.resolve()
    return resolved == resolved_root or resolved_root in resolved.parents
