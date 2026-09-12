from pathlib import Path

from app.storage.local import LocalStorage


def test_round_trip(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "storage")

    stored = storage.put(key="ws/b/f.pdf", data=b"abc", content_type="application/pdf")

    assert stored.size == 3
    assert storage.exists("ws/b/f.pdf")
    assert storage.get("ws/b/f.pdf") == b"abc"
    storage.delete("ws/b/f.pdf")
    assert not storage.exists("ws/b/f.pdf")


def test_rejects_escaping_keys(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)

    for bad in ["../escape.pdf", "/abs/path.pdf", "a/../../b.pdf", ""]:
        try:
            storage.put(key=bad, data=b"x")
        except ValueError:
            continue
        raise AssertionError(f"key {bad!r} should have been rejected")
