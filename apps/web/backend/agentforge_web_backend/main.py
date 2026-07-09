from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from agentforge.runs.service import RunService

from .config import MAX_REQUEST_BODY_BYTES, MAX_UPLOAD_BODY_BYTES, default_frontend_dist
from .legacy_bridge import dispatch_legacy_request, is_legacy_api_path
from .static import frontend_response
from .uploads import resolve_uploaded_file, save_uploaded_files


def create_app(project_root: Path | str = ".", frontend_dist: Path | str | None = None) -> FastAPI:
    root = Path(project_root).resolve()
    app = FastAPI(title="AgentForge Web API", version="0.1.0")
    app.state.project_root = root
    app.state.frontend_dist = Path(frontend_dist).resolve() if frontend_dist is not None else default_frontend_dist(root)
    RunService(root).ensure_initialized()

    @app.middleware("http")
    async def reject_oversized_body(request: Request, call_next):  # type: ignore[no-untyped-def]
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                byte_count = int(content_length)
            except ValueError:
                return JSONResponse({"error": "Content-Length must be an integer."}, status_code=400)
            max_body_bytes = MAX_UPLOAD_BODY_BYTES if request.url.path == "/api/uploads" else MAX_REQUEST_BODY_BYTES
            if byte_count > max_body_bytes:
                async for _ in request.stream():
                    pass
                return JSONResponse(
                    {"error": f"Request body exceeds {max_body_bytes} bytes."},
                    status_code=413,
                )
        return await call_next(request)

    @app.post("/api/uploads")
    async def upload_files(files: list[UploadFile] = File(...)) -> JSONResponse:
        try:
            uploads = await save_uploaded_files(root, files)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse({"uploads": uploads})

    @app.get("/api/uploads/{relative_path:path}")
    async def get_uploaded_file(relative_path: str) -> Response:
        try:
            path = resolve_uploaded_file(root, relative_path)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except FileNotFoundError:
            return JSONResponse({"error": "Uploaded file not found."}, status_code=404)
        return FileResponse(path)

    @app.api_route("/api/{path:path}", methods=["GET", "POST"])
    async def api_dispatch(path: str, request: Request) -> Response:
        return await dispatch_legacy_request(request, path, prefix_api_urls=True)

    @app.api_route("/{path:path}", methods=["GET", "POST"])
    async def legacy_api_or_frontend(path: str, request: Request) -> Response:
        if is_legacy_api_path(path):
            return await dispatch_legacy_request(request, path, prefix_api_urls=False)
        if request.method != "GET":
            return JSONResponse({"error": "Route not found.", "path": f"/{path}"}, status_code=404)
        return frontend_response(path, request.app.state.frontend_dist)

    return app


def run_server(project_root: Path | str = ".", host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    root = Path(project_root).resolve()
    app = create_app(root)
    print(f"AgentForge FastAPI listening on http://{host}:{port}")
    print(f"AgentForge API: http://{host}:{port}/api")
    print(f"AgentForge Web: http://{host}:{port}/")
    print(f"Project root: {root}")
    uvicorn.run(app, host=host, port=port, log_level="info")
