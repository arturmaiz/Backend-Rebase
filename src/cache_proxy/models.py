from dataclasses import dataclass


@dataclass(frozen=True)
class CachedBlob:
    body: bytes
    headers: dict[str, str]
    media_type: str
    status_code: int
