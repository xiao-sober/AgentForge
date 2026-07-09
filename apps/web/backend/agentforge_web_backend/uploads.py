from __future__ import annotations

import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile

from .config import MAX_UPLOAD_FILE_BYTES, MAX_UPLOAD_FILES

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
CODE_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".css",
    ".scss",
    ".html",
    ".htm",
    ".sql",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
}
DOCUMENT_SUFFIXES = {".txt", ".md", ".markdown", ".rst", ".adoc", ".pdf", ".doc", ".docx", ".rtf"}
DATA_SUFFIXES = {".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".xls", ".xlsx"}
PRESENTATION_SUFFIXES = {".ppt", ".pptx"}

ALLOWED_UPLOAD_SUFFIXES = (
    IMAGE_SUFFIXES | CODE_SUFFIXES | DOCUMENT_SUFFIXES | DATA_SUFFIXES | PRESENTATION_SUFFIXES
)

ANALYZABLE_CODE_SUFFIXES = CODE_SUFFIXES | {".json"}
ANALYZABLE_DOCUMENT_SUFFIXES = {".txt", ".md", ".markdown", ".rst", ".adoc", ".html", ".htm"}
ANALYZABLE_DATA_SUFFIXES = {".csv", ".tsv", ".json", ".jsonl", ".ndjson"}


async def save_uploaded_files(project_root: Path, files: list[UploadFile]) -> list[dict[str, Any]]:
    if not files:
        raise ValueError("No files uploaded.")
    if len(files) > MAX_UPLOAD_FILES:
        raise ValueError(f"Upload accepts at most {MAX_UPLOAD_FILES} files at a time.")

    upload_base = (project_root / "data" / "uploads").resolve()
    upload_dir = upload_base / datetime.now(timezone.utc).strftime("%Y%m%d")
    upload_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for upload in files:
        original_name = Path(upload.filename or "upload").name
        safe_name = _safe_filename(original_name)
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_UPLOAD_SUFFIXES:
            raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")

        stored_name = f"{uuid4().hex}_{safe_name}"
        target = (upload_dir / stored_name).resolve()
        if upload_base != target and upload_base not in target.parents:
            raise ValueError("Upload path must stay under data/uploads.")

        size_bytes = 0
        try:
            with target.open("wb") as output:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    if size_bytes > MAX_UPLOAD_FILE_BYTES:
                        raise ValueError(f"{original_name} exceeds {MAX_UPLOAD_FILE_BYTES} bytes.")
                    output.write(chunk)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

        day_relative_path = target.relative_to(upload_base).as_posix()
        record = {
            "upload_id": uuid4().hex,
            "original_name": original_name,
            "stored_name": stored_name,
            "relative_path": target.relative_to(project_root).as_posix(),
            "url": f"/api/uploads/{day_relative_path}",
            "content_type": upload.content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream",
            "size_bytes": size_bytes,
            "kind": _file_kind(suffix),
            "supported_tasks": _supported_tasks(suffix),
        }
        records.append(record)

    return records


def resolve_uploaded_file(project_root: Path, relative_path: str) -> Path:
    upload_base = (project_root / "data" / "uploads").resolve()
    target = (upload_base / relative_path).resolve()
    if upload_base != target and upload_base not in target.parents:
        raise ValueError("Upload path must stay under data/uploads.")
    if not target.is_file():
        raise FileNotFoundError(relative_path)
    return target


def _safe_filename(filename: str) -> str:
    path = Path(filename.strip() or "upload")
    suffix = path.suffix.lower()
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", path.stem).strip("_-") or "upload"
    safe_suffix = re.sub(r"[^A-Za-z0-9.]+", "", suffix)
    return f"{stem[:96]}{safe_suffix[:20]}" or "upload"


def _file_kind(suffix: str) -> str:
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in ANALYZABLE_DATA_SUFFIXES or suffix in DATA_SUFFIXES:
        return "data"
    if suffix in ANALYZABLE_DOCUMENT_SUFFIXES or suffix in DOCUMENT_SUFFIXES:
        return "document"
    if suffix in ANALYZABLE_CODE_SUFFIXES:
        return "code"
    return "file"


def _supported_tasks(suffix: str) -> list[str]:
    tasks: list[str] = []
    if suffix in ANALYZABLE_CODE_SUFFIXES:
        tasks.append("code_analysis")
    if suffix in ANALYZABLE_DOCUMENT_SUFFIXES:
        tasks.append("document_analysis")
    if suffix in ANALYZABLE_DATA_SUFFIXES:
        tasks.append("data_analysis")
    return tasks
