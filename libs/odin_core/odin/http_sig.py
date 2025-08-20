"""HTTP response signing helpers (Ed25519) with canonical message.

Header format:
  v=1;ts_ns=<ns>;alg=Ed25519;kid=<kid>;hash=<b64u(blake3(body))>;sig=<b64u(sig)>

Canonical message bytes:
  b"ODIN-HTTP-SIG.v1\n" +
  f"ts_ns:{ts_ns}\n" +
  f"method:{METHOD}\n" +
  f"path:{PATH}\n" +
  f"hash:{B64U(blake3_256(body))}\n"
"""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .crypto.blake3_hash import blake3_256_b64u


def _b64u_nopad(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * ((4 - len(s) % 4) % 4))


CANON_PREFIX = b"ODIN-HTTP-SIG.v1\n"


def _content_hash_b64u(body: bytes) -> str:
    return blake3_256_b64u(body)


def _build_message(ts_ns: int, method: str, path: str, content_hash_b64u: str) -> bytes:
    parts = [
        CANON_PREFIX,
        f"ts_ns:{ts_ns}\n".encode("ascii"),
        f"method:{method.upper()}\n".encode("ascii"),
        f"path:{path}\n".encode("utf-8"),
        f"hash:{content_hash_b64u}\n".encode("ascii"),
    ]
    return b"".join(parts)


@dataclass
class HttpSig:
    v: int
    ts_ns: int
    alg: str
    kid: str
    hash_b64u: str
    sig_b64u: str

    def to_header(self) -> str:
        return (
            f"v={self.v};ts_ns={self.ts_ns};alg={self.alg};kid={self.kid};"
            f"hash={self.hash_b64u};sig={self.sig_b64u}"
        )


def sign_v1(
    *, method: str, path: str, body: bytes, kid: str, priv: Ed25519PrivateKey, ts_ns: Optional[int] = None
) -> str:
    if ts_ns is None:
        ts_ns = time.time_ns()
    h = _content_hash_b64u(body)
    msg = _build_message(ts_ns, method, path, h)
    sig = priv.sign(msg)
    return HttpSig(v=1, ts_ns=ts_ns, alg="Ed25519", kid=kid, hash_b64u=h, sig_b64u=_b64u_nopad(sig)).to_header()


def _parse_header(header: str) -> Dict[str, str]:
    parts = [p.strip() for p in header.split(";") if p.strip()]
    kv: Dict[str, str] = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            kv[k.strip()] = v.strip()
    return kv


def verify_v1(
    *, method: str, path: str, body: bytes, header: str, jwks: Dict[str, Any]
) -> Dict[str, Any]:
    kv = _parse_header(header)
    if kv.get("v") != "1" or kv.get("alg") != "Ed25519":
        raise ValueError("unsupported http signature")
    kid = kv.get("kid")
    ts_ns_str = kv.get("ts_ns")
    h_recv = kv.get("hash")
    sig_b64u = kv.get("sig")
    if not all([kid, ts_ns_str, h_recv, sig_b64u]):
        raise ValueError("invalid http signature header")

    # Validate content hash matches
    h = _content_hash_b64u(body)
    if h != h_recv:
        raise ValueError("content hash mismatch")

    # Resolve JWK by kid (OKP/Ed25519)
    keys = jwks.get("keys", [])
    key = next((k for k in keys if k.get("kid") == kid and k.get("kty") == "OKP" and k.get("crv") == "Ed25519"), None)
    if not key:
        raise ValueError("unknown kid")

    x_b64u = key.get("x")
    pub = Ed25519PublicKey.from_public_bytes(_b64u_decode(x_b64u))
    msg = _build_message(int(ts_ns_str), method, path, h)
    pub.verify(_b64u_decode(sig_b64u), msg)
    return {"ok": True, "kid": kid, "ts_ns": int(ts_ns_str)}
