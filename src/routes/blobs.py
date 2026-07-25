from fastapi import APIRouter, HTTPException, Request, Response, status

from config import MAX_PAYLOAD_LENGTH
from validation import InvalidBlobId, validate_blob_id


router = APIRouter()


# POST /blobs/{blob_id} — store or overwrite a blob
@router.post("/{blob_id}")
def store_blob(blob_id: str, request: Request):
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
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="payload exceeds maximum allowed size",
        )

    # TODO: validate payload length, disk quota, blob count

    # TODO: extract storable headers:
    # Content-Type and x-rebase-*

    # TODO: validate header constraints

    # TODO: stream body to disk

    # TODO: persist metadata containing the stored headers

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

    # TODO: check whether the blob exists
    # Return 404 if it does not

    # TODO: read stored headers and add them to the response

    # TODO: use application/octet-stream if Content-Type was not stored

    # TODO: stream the file into the response

    return Response(
        status_code=status.HTTP_404_NOT_FOUND,
        media_type="application/json",
        content='{"error": "not found"}',
    )


# DELETE /blobs/{blob_id} — delete a blob
@router.delete("/{blob_id}")
def delete_blob(blob_id: str):
    try:
        validate_blob_id(blob_id)
    except InvalidBlobId as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # TODO: delete the blob and its metadata
    # No 404 is required if they do not exist

    return Response(status_code=status.HTTP_204_NO_CONTENT)