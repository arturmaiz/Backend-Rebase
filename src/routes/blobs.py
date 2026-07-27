import asyncio
import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response, status
from starlette.requests import ClientDisconnect
from starlette.responses import StreamingResponse

from config import (
    DATA_DIR,
    MAX_BLOBS_TOTAL,
    MAX_DISK_QUOTA,
    MAX_PAYLOAD_LENGTH,
    STREAM_CHUNK_SIZE,
)
from validation import (
    InvalidBlobId,
    InvalidHeaders,
    validate_blob_id,
    validate_stored_headers,
)


router = APIRouter()

# Protects quota/count checks and mutations across concurrent requests to different ids.
# Same-id concurrency is excluded by the assignment.
_storage_lock = asyncio.Lock()

BLOBS_ROOT = DATA_DIR / "blobs"
STAGING_ROOT = BLOBS_ROOT / ".staging"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(text)
    temp_path.replace(path)


def _scan_storage() -> tuple[int, int]:
    """Count only committed blobs (directories with a finalized data file)."""
    existing_count = 0
    existing_total_bytes = 0
    if not BLOBS_ROOT.exists():
        return existing_count, existing_total_bytes

    for entry in BLOBS_ROOT.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue

        data_file = entry / "data"
        if not data_file.exists():
            continue

        existing_count += 1
        existing_total_bytes += data_file.stat().st_size

    return existing_count, existing_total_bytes


def cleanup_temp_files() -> None:
    """Remove leftover staging dirs and temp files from interrupted writes."""
    if STAGING_ROOT.exists():
        shutil.rmtree(STAGING_ROOT, ignore_errors=True)

    if not BLOBS_ROOT.exists():
        return

    for entry in BLOBS_ROOT.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue

        data_file = entry / "data"
        for temp_file in entry.glob("*.tmp"):
            temp_file.unlink(missing_ok=True)

        # Drop blob dirs that never finished committing a data file.
        if not data_file.exists() and not any(entry.iterdir()):
            entry.rmdir()


async def _stream_body_to_file(
    request: Request,
    dest: Path,
    expected_length: int,
) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = 0

    with dest.open("wb") as file:
        try:
            async for chunk in request.stream():
                total += len(chunk)
                if total > expected_length:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="request body exceeds Content-Length",
                    )
                if total > MAX_PAYLOAD_LENGTH:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="payload exceeds maximum allowed size",
                    )

                file.write(chunk)
        except ClientDisconnect:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="client disconnected before upload completed",
            )

    if total != expected_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="request body size does not match Content-Length",
        )

    return total


def _iter_file_chunks(path: Path, chunk_size: int):
    with path.open("rb") as file:
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            yield chunk


def _check_limits(
    *,
    already_exists: bool,
    existing_count: int,
    existing_total_bytes: int,
    replaced_bytes: int,
    new_bytes: int,
) -> None:
    new_count = existing_count if already_exists else existing_count + 1
    if new_count > MAX_BLOBS_TOTAL:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="maximum number of stored blobs exceeded",
        )

    new_total_bytes = existing_total_bytes - replaced_bytes + new_bytes
    if new_total_bytes > MAX_DISK_QUOTA:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="storage quota exceeded",
        )


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

    if content_length < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content-Length must not be negative",
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

    staging_dir = STAGING_ROOT / f"{blob_id}.{uuid.uuid4().hex}"
    staging_data = staging_dir / "data"

    try:
        await _stream_body_to_file(request, staging_data, content_length)

        target_dir = BLOBS_ROOT / blob_id
        async with _storage_lock:
            already_exists = (target_dir / "data").exists()
            existing_count, existing_total_bytes = _scan_storage()

            replaced_bytes = 0
            if already_exists:
                replaced_bytes = (target_dir / "data").stat().st_size

            _check_limits(
                already_exists=already_exists,
                existing_count=existing_count,
                existing_total_bytes=existing_total_bytes,
                replaced_bytes=replaced_bytes,
                new_bytes=content_length,
            )

            target_dir.mkdir(parents=True, exist_ok=True)
            staging_data.replace(target_dir / "data")
            _atomic_write_text(
                target_dir / "metadata.json",
                json.dumps(stored_headers),
            )
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

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

    return StreamingResponse(
        _iter_file_chunks(data_file, STREAM_CHUNK_SIZE),
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
