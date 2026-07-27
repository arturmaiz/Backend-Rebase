import json
import shutil

from fastapi import APIRouter, HTTPException, Request, Response, status

from config import DATA_DIR, MAX_BLOBS_TOTAL, MAX_DISK_QUOTA, MAX_PAYLOAD_LENGTH
from validation import (
    InvalidBlobId,
    InvalidHeaders,
    validate_blob_id,
    validate_stored_headers,
)


router = APIRouter()


# POST /blobs/{blob_id} — store or overwrite a blob
@router.post("/{blob_id}")
async def store_blob(blob_id: str, request: Request):
    try:
        validate_blob_id(blob_id)
    except InvalidBlobId as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # requiring the client to declare the payload size up front
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

    # rejectig payloads larger than the allowed maximum (by declared size)
    if content_length > MAX_PAYLOAD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="payload exceeds maximum allowed size",
        )

    # keeping only the headers we are allowed to store (Content-Type and x-rebase-*)
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

    # verifying the bytes we actually received match the declared size
    if len(body) != content_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="request body size does not match Content-Length",
        )

    blobs_root = DATA_DIR / "blobs"
    directory = blobs_root / blob_id
    already_exists = directory.exists()

    # Scanning current storage to enforce blob-count and disk-quota limits.
    existing_count = 0
    existing_total_bytes = 0
    if blobs_root.exists():
        for entry in blobs_root.iterdir():
            if not entry.is_dir():
                continue
            existing_count += 1
            data_file = entry / "data"
            if data_file.exists():
                existing_total_bytes += data_file.stat().st_size

    # rejecting if this would push the total blob count over the limit
    new_count = existing_count if already_exists else existing_count + 1
    if new_count > MAX_BLOBS_TOTAL:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="maximum number of stored blobs exceeded",
        )

    # rejecting if the resulting total size would exceed the disk quota
    # (subtracting the old bytes first when overwriting an existing blob)
    replaced_bytes = 0
    if already_exists and (directory / "data").exists():
        replaced_bytes = (directory / "data").stat().st_size

    new_total_bytes = existing_total_bytes - replaced_bytes + len(body)
    if new_total_bytes > MAX_DISK_QUOTA:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="storage quota exceeded",
        )

    # Actually storing the payload and headers
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "data").write_bytes(body)
    (directory / "metadata.json").write_text(json.dumps(stored_headers))

    return Response(
        status_code=status.HTTP_201_CREATED,
        media_type="application/json",
        content='{"message": "created"}',
    )


# GET /blobs/{blob_id} — retrieve a blob
@router.get("/{blob_id}")
def get_blob(blob_id: str):
    try:
        validate_blob_id(blob_id)
    except InvalidBlobId as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # returning 404 if the blob does not exist
    directory = DATA_DIR / "blobs" / blob_id
    data_file = directory / "data"
    if not data_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="blob not found",
        )

    # loading the headers that were stored alongside the blob (if any)
    metadata_file = directory / "metadata.json"
    stored_headers = {}
    if metadata_file.exists():
        stored_headers = json.loads(metadata_file.read_text())

    # pulling Content-Type out to set it once; use octet-stream as default
    content_type = stored_headers.pop("content-type", "application/octet-stream")

    return Response(
        content=data_file.read_bytes(),
        media_type=content_type,
        headers=stored_headers,
    )


# DELETE /blobs/{blob_id} — delete a blob
@router.delete("/{blob_id}")
def delete_blob(blob_id: str):
    try:
        validate_blob_id(blob_id)
    except InvalidBlobId as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # removing the blob directory; a missing blob is treated as already deleted
    directory = DATA_DIR / "blobs" / blob_id
    if directory.exists():
        shutil.rmtree(directory)

    return Response(status_code=status.HTTP_204_NO_CONTENT)