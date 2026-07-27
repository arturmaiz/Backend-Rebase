from config import (
    MAX_HEADER_COUNT,
    MAX_HEADER_KEY_LENGTH,
    MAX_HEADER_VALUE_LENGTH,
    MAX_ID_LENGTH,
    VALID_ID_PATTERN,
)


class InvalidBlobId(Exception):
    """Raised when a blob id breaks one of our id rules."""


class InvalidHeaders(Exception):
    """Raised when the headers we intend to store break one of our rules."""


def validate_blob_id(blob_id: str) -> None:
    if not blob_id:
        raise InvalidBlobId("id must not be empty")

    # "." / ".." resolve outside the blob storage directory.
    if blob_id in {".", ".."}:
        raise InvalidBlobId("id contains invalid characters")

    if len(blob_id) > MAX_ID_LENGTH:
        raise InvalidBlobId("id exceeds maximum length")

    if not VALID_ID_PATTERN.match(blob_id):
        raise InvalidBlobId("id contains invalid characters")


def validate_stored_headers(headers: dict) -> None:
    if len(headers) > MAX_HEADER_COUNT:
        raise InvalidHeaders("too many stored headers")

    for key, value in headers.items():
        if len(key) > MAX_HEADER_KEY_LENGTH:
            raise InvalidHeaders("stored header key exceeds maximum length")

        if len(value) > MAX_HEADER_VALUE_LENGTH:
            raise InvalidHeaders("stored header value exceeds maximum length")
