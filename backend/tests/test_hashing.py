from app.core.hashing import sha256_hex


def test_sha256_hex_is_stable() -> None:
    assert sha256_hex(b"hello") == sha256_hex(b"hello")
    assert (
        sha256_hex(b"hello")
        == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )
