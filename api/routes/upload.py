"""POST /api/upload — accept a WAV file, save to disk, register in UPLOAD_REGISTRY."""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from api.models import UploadResponse
from api.uploads import UPLOAD_REGISTRY

router = APIRouter()

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/api/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    """Accept a WAV file upload, save it to UPLOAD_DIR, register it in UPLOAD_REGISTRY."""
    file_id = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{file_id}_{file.filename}"
    with dest.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)
    # MUST be set before returning — process.py depends on this
    UPLOAD_REGISTRY[file_id] = str(dest.resolve())
    return UploadResponse(file_id=file_id, filename=file.filename, path=str(dest))


@router.get("/api/upload/{file_id}/audio")
async def get_upload_audio(file_id: str) -> FileResponse:
    """Return the original uploaded WAV file by file_id.

    Used by the React frontend as a fallback when the blob URL created from
    the uploaded File is not available (e.g., after page refresh).
    """
    path = UPLOAD_REGISTRY.get(file_id)
    if path is None or not Path(path).exists():
        raise HTTPException(
            status_code=404,
            detail=f"file_id '{file_id}' not found or file missing",
        )
    return FileResponse(path, media_type="audio/wav")
