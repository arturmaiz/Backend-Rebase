from config import MAX_ID_LENGTH, VALID_ID_PATTERN


class InvalidBlobId(Exception):
    """Raised when a blob id breaks one of our id rules."""


def validate_blob_id(blob_id: str) -> None:
    if not blob_id:
        raise InvalidBlobId("id must not be empty")

    if len(blob_id) > MAX_ID_LENGTH:
        raise InvalidBlobId("id exceeds maximum length")

    if not VALID_ID_PATTERN.match(blob_id):
        raise InvalidBlobId("id contains invalid characters")
