from pathlib import Path

from app.storage.protocols import StoredObject


class LocalStorage:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def _resolve(self, key: str) -> Path:
        if not key or key.startswith("/") or ".." in Path(key).parts:
            raise ValueError(f"invalid storage key: {key!r}")
        path = (self._root / key).resolve()
        if self._root != path and self._root not in path.parents:
            raise ValueError(f"storage key escapes root: {key!r}")
        return path

    def put(self, *, key: str, data: bytes, content_type: str | None = None) -> StoredObject:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(key=key, size=len(data), content_type=content_type)

    def get(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()
