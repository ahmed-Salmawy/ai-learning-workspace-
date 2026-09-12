from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class StoredObject:
    key: str
    size: int
    content_type: str | None


@runtime_checkable
class ObjectStorage(Protocol):
    def put(self, *, key: str, data: bytes, content_type: str | None = None) -> StoredObject: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...
