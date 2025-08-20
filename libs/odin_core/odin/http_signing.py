from __future__ import annotations

import base64
import hashlib


def _b64u_no_pad(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def body_sha256_b64u(body: bytes | bytearray | memoryview) -> str:
    """Compute base64url (unpadded) SHA-256 of the request body bytes."""
    if isinstance(body, (bytearray, memoryview)):
        body = bytes(body)
    h = hashlib.sha256(body).digest()
    return _b64u_no_pad(h)


def build_http_signing_message(ts_ns: int, method: str, path_with_query: str, body: bytes) -> bytes:
    """Construct the canonical message to sign for HTTP requests.

    Format (UTF-8 bytes):
      v1\n{ts_ns}\n{METHOD}\n{path_with_query}\n{sha256_b64u(body)}
    """
    m = method.upper()
    bh = body_sha256_b64u(body)
    return f"v1\n{ts_ns}\n{m}\n{path_with_query}\n{bh}".encode("utf-8")


__all__ = ["body_sha256_b64u", "build_http_signing_message"]
