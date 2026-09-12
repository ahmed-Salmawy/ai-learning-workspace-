from app.storage.protocols import StoredObject


class InMemoryObjectStorage:
    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str | None]] = {}

    def put(self, *, key: str, data: bytes, content_type: str | None = None) -> StoredObject:
        self._objects[key] = (data, content_type)
        return StoredObject(key=key, size=len(data), content_type=content_type)

    def get(self, key: str) -> bytes:
        return self._objects[key][0]

    def delete(self, key: str) -> None:
        del self._objects[key]

    def exists(self, key: str) -> bool:
        return key in self._objects
