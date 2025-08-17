# path: libs/odin_core/odin/crypto/blake3_hash.py
"""Lightweight BLAKE3 hashing helpers."""
from __future__ import annotations

from base64 import urlsafe_b64encode
from blake3 import blake3


def blake3_256(data: bytes) -> bytes:
    """Return 32-byte BLAKE3 digest for the given data."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("data must be bytes-like")
    return blake3(data).digest(length=32)


def blake3_256_b64u(data: bytes) -> str:
    """Return URL-safe base64 (no padding) of 32-byte BLAKE3 digest."""
    digest = blake3_256(data)
    return urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
