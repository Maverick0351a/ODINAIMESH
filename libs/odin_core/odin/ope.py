# path: libs/odin_core/odin/ope.py
"""ODIN Proof Envelope (OPE) signing and verification.

Message format:
- prefix: b"ODIN:OPE:v1"
- message: prefix + '|' + ts_ns(8 bytes big-endian) + '|' + blake3(content_bytes) + optional '|' + oml_cid
- returns JSON: {v, alg, ts_ns, kid, pub_b64u, content_hash_b3_256_b64u, sig_b64u, oml_cid?}
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any
from base64 import urlsafe_b64encode, urlsafe_b64decode
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
import time

from .crypto.blake3_hash import blake3_256, blake3_256_b64u

PREFIX = b"ODIN:OPE:v1"
ALG = "Ed25519"
VERSION = 1


@dataclass
class OpeKeypair:
    kid: str
    private_key: Ed25519PrivateKey
    public_key: Ed25519PublicKey

    @staticmethod
    def generate(kid: str = "k1") -> "OpeKeypair":
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key()
        return OpeKeypair(kid=kid, private_key=priv, public_key=pub)

    def pub_b64u(self) -> str:
        raw = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    def priv_b64u(self) -> str:
        raw = self.private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


_def_now_ns = lambda: time.time_ns()


def _build_message(ts_ns: int, content_bytes: bytes, oml_cid: Optional[str]) -> bytes:
    if not isinstance(content_bytes, (bytes, bytearray, memoryview)):
        raise TypeError("content_bytes must be bytes-like")
    parts = [PREFIX, b"|"]
    ts_be = ts_ns.to_bytes(8, "big", signed=False)
    parts.append(ts_be)
    parts.append(b"|")
    parts.append(blake3_256(content_bytes))
    if oml_cid:
        parts.append(b"|")
        parts.append(oml_cid.encode("ascii"))
    return b"".join(parts)


def sign_over_content(keypair: OpeKeypair, content_bytes: bytes, oml_cid: Optional[str] = None, *, ts_ns: Optional[int] = None) -> Dict[str, Any]:
    ts = _def_now_ns() if ts_ns is None else int(ts_ns)
    msg = _build_message(ts, content_bytes, oml_cid)
    sig = keypair.private_key.sign(msg)

    return {
        "v": VERSION,
        "alg": ALG,
        "ts_ns": ts,
        "kid": keypair.kid,
        "pub_b64u": keypair.pub_b64u(),
        "content_hash_b3_256_b64u": blake3_256_b64u(content_bytes),
        "sig_b64u": urlsafe_b64encode(sig).rstrip(b"=").decode("ascii"),
        **({"oml_cid": oml_cid} if oml_cid else {}),
    }


def verify_over_content(
    ope: Dict[str, Any],
    content_bytes: bytes,
    expected_oml_cid: Optional[str] = None,
    max_skew_ns: Optional[int] = None,
) -> Dict[str, Any]:
    try:
        if not isinstance(ope, dict):
            return {"ok": False, "reason": "ope_not_dict"}
        v = ope.get("v")
        alg = ope.get("alg")
        ts_ns = int(ope.get("ts_ns"))
        kid = ope.get("kid")
        pub_b64u = ope.get("pub_b64u")
        content_hash_b64u = ope.get("content_hash_b3_256_b64u")
        sig_b64u = ope.get("sig_b64u")
        oml_cid = ope.get("oml_cid")

        if v != VERSION or alg != ALG:
            return {"ok": False, "reason": "version_or_alg_mismatch"}
        if not isinstance(kid, str) or not isinstance(pub_b64u, str) or not isinstance(sig_b64u, str):
            return {"ok": False, "reason": "missing_fields"}

        # Content hash must match
        expected_hash = blake3_256_b64u(content_bytes)
        if content_hash_b64u != expected_hash:
            return {"ok": False, "reason": "content_hash_mismatch"}

        # Expected OML CID if provided must match
        if expected_oml_cid is not None and oml_cid != expected_oml_cid:
            return {"ok": False, "reason": "oml_cid_mismatch"}

        # Time skew check
        if max_skew_ns is not None:
            now = _def_now_ns()
            if abs(now - ts_ns) > int(max_skew_ns):
                return {"ok": False, "reason": "ts_skew"}

        # Verify signature
        pub_raw = urlsafe_b64decode(pub_b64u + "==")
        sig_raw = urlsafe_b64decode(sig_b64u + "==")
        pub = Ed25519PublicKey.from_public_bytes(pub_raw)
        msg = _build_message(ts_ns, content_bytes, oml_cid)
        pub.verify(sig_raw, msg)
        return {"ok": True, "kid": kid}
    except Exception as e:
        return {"ok": False, "reason": "verify_error:" + str(e)}
