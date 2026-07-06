from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from agentforge.web.routes import WebResponse, handle_request

from .config import MAX_REQUEST_BODY_BYTES

LEGACY_API_PATHS = {
    "health",
    "version",
    "config",
    "chat",
    "skills",
    "tasksets",
    "memory",
    "traces",
    "hqs",
}

LEGACY_API_PREFIXES = ("agent/runs/", "skills/", "traces/")


async def dispatch_legacy_request(request: Request, path: str, *, prefix_api_urls: bool = True) -> Response:
    body = await request.body()
    if len(body) > MAX_REQUEST_BODY_BYTES:
        return JSONResponse(
            {"error": f"Request body exceeds {MAX_REQUEST_BODY_BYTES} bytes."},
            status_code=413,
        )
    legacy_response = handle_request(
        request.method,
        _raw_path(path, request),
        body=body,
        project_root=request.app.state.project_root,
    )
    return to_fastapi_response(legacy_response, prefix_api_urls=prefix_api_urls)


def is_legacy_api_path(path: str) -> bool:
    return path in LEGACY_API_PATHS or path.startswith(LEGACY_API_PREFIXES)


def to_fastapi_response(response: WebResponse, *, prefix_api_urls: bool = True) -> Response:
    content_type = (response.headers or {}).get("Content-Type", "")
    if response.body_text is None and response.body_bytes is None and "application/json" in content_type:
        payload = _prefix_api_urls(response.payload) if prefix_api_urls else response.payload
        return JSONResponse(payload, status_code=response.status)
    headers = {key: value for key, value in (response.headers or {}).items() if key.lower() != "content-length"}
    return Response(content=response.body(), status_code=response.status, headers=headers)


def _raw_path(path: str, request: Request) -> str:
    raw_path = f"/{path}"
    if request.url.query:
        raw_path = f"{raw_path}?{request.url.query}"
    return raw_path


def _prefix_api_urls(value: Any) -> Any:
    if isinstance(value, dict):
        transformed: dict[str, Any] = {}
        for key, item in value.items():
            if key.endswith("_url") and isinstance(item, str) and item.startswith("/") and not item.startswith("/api/"):
                transformed[key] = f"/api{item}"
            else:
                transformed[key] = _prefix_api_urls(item)
        return transformed
    if isinstance(value, list):
        return [_prefix_api_urls(item) for item in value]
    return value
