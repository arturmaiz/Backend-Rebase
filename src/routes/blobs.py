import asyncio
import json
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response, status

from config import DATA_DIR, MAX_BLOBS_TOTAL, MAX_DISK_QUOTA, MAX_PAYLOAD_LENGTH
from validation import (
    InvalidBlobId,
    InvalidHeaders,
    validate_blob_id,
    validate_stored_headers,
)


router = APIRouter()

# Serializes quota checks and all read/write/delete operations within this process.
_storage_lock = asyncio.Lock()

BLOBS_ROOT = DATA_DIR / "blobs"


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_bytes(data)
    temp_path.replace(path)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(text)
    temp_path.replace(path)


def _scan_storage() -> tuple[int, int]:
    existing_count = 0
    existing_total_bytes = 0
    if not BLOBS_ROOT.exists():
        return existing_count, existing_total_bytes

    for entry in BLOBS_ROOT.iterdir():
        if not entry.is_dir():
            continue
        existing_count += 1
        data_file = entry / "data"
        if data_file.exists():
            existing_total_bytes += data_file.stat().st_size

    return existing_count, existing_total_bytes


def cleanup_temp_files() -> None:
    """Remove leftover temp files from interrupted writes."""
    if not BLOBS_ROOT.exists():
        return

    for entry in BLOBS_ROOT.iterdir():
        if not entry.is_dir():
            continue
        for temp_file in entry.glob("*.tmp"):
            temp_file.unlink(missing_ok=True)


# POST /blobs/{blob_id} — store or overwrite a blob
@router.post("/{blob_id}")
async def store_blob(blob_id: str, request: Request):
    try:
        validate_blob_id(blob_id)
    except InvalidBlobId as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    content_length_header = request.headers.get("content-length")
    if content_length_header is None:
        raise HTTPException(
            status_code=status.HTTP_411_LENGTH_REQUIRED,
            detail="Content-Length header is required",
        )

    try:
        content_length = int(content_length_header)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content-Length header is not a valid integer",
        )

    if content_length > MAX_PAYLOAD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="payload exceeds maximum allowed size",
        )

    stored_headers = {}
    for name, value in request.headers.items():
        lower_name = name.lower()
        if lower_name == "content-type" or lower_name.startswith("x-rebase-"):
            stored_headers[lower_name] = value

    try:
        validate_stored_headers(stored_headers)
    except InvalidHeaders as exc:
        raise HTTPException(
            status_code=status.HTTP_431_REQUEST_HEADER_FIELDS_TOO_LARGE,
            detail=str(exc),
        )

    body = await request.body()

    if len(body) != content_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="request body size does not match Content-Length",
        )

    directory = BLOBS_ROOT / blob_id

    async with _storage_lock:
        already_exists = directory.exists()
        existing_count, existing_total_bytes = _scan_storage()

        new_count = existing_count if already_exists else existing_count + 1
        if new_count > MAX_BLOBS_TOTAL:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="maximum number of stored blobs exceeded",
            )

        replaced_bytes = 0
        if already_exists and (directory / "data").exists():
            replaced_bytes = (directory / "data").stat().st_size

        new_total_bytes = existing_total_bytes - replaced_bytes + len(body)
        if new_total_bytes > MAX_DISK_QUOTA:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="storage quota exceeded",
            )

        _atomic_write_bytes(directory / "data", body)
        _atomic_write_text(directory / "metadata.json", json.dumps(stored_headers))

    return Response(
        status_code=status.HTTP_201_CREATED,
        media_type="application/json",
        content='{"message": "created"}',
    )


# GET /blobs/{blob_id} — retrieve a blob
@router.get("/{blob_id}")
async def get_blob(blob_id: str):
    try:
        validate_blob_id(blob_id)
    except InvalidBlobId as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    async with _storage_lock:
        directory = BLOBS_ROOT / blob_id
        data_file = directory / "data"
        if not data_file.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="blob not found",
            )

        metadata_file = directory / "metadata.json"
        stored_headers = {}
        if metadata_file.exists():
            stored_headers = json.loads(metadata_file.read_text())

        content_type = stored_headers.pop("content-type", "application/octet-stream")
        body = data_file.read_bytes()

    return Response(
        content=body,
        media_type=content_type,
        headers=stored_headers,
    )


# DELETE /blobs/{blob_id} — delete a blob
@router.delete("/{blob_id}")
async def delete_blob(blob_id: str):
    try:
        validate_blob_id(blob_id)
    except InvalidBlobId as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    async with _storage_lock:
        directory = BLOBS_ROOT / blob_id
        if directory.exists():
            shutil.rmtree(directory)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
