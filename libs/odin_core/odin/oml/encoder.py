# path: libs/odin_core/odin/oml/encoder.py
"""OML-C encoding, CID, and optional transport frame.

Steps for OML-C:
1) Normalize all strings to NFC deterministically
2) Apply symbol table (SFT) for compact/int keys and enum-like values
3) Encode to CBOR with canonical ordering
"""
from __future__ import annotations

from typing import Any, Dict, Tuple
import unicodedata
import cbor2
from blake3 import blake3
import base64

from .symbols import sym, get_default_sft


# --------- helpers ---------
def _nfc(obj: Any) -> Any:
    """Normalize all strings to NFC recursively for determinism."""
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, list):
        return [_nfc(x) for x in obj]
    if isinstance(obj, dict):
        return { _nfc(k): _nfc(v) for k, v in obj.items() }
    return obj


def _apply_symbols(obj: Any, sft: Dict[str, int]) -> Any:
    """Replace common map keys & enum-like values with integer symbols when known."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            k2 = sym(str(k), sft)
            out[k2] = _apply_symbols(v, sft)
        return out
    if isinstance(obj, list):
        return [_apply_symbols(x, sft) for x in obj]
    if isinstance(obj, str):
        # also symbol-substitute certain enum values (intents)
        maybe = sym(obj, sft)
        return maybe
    return obj


# --------- public API ---------
def to_oml_c(payload: Dict[str, Any], *, sft: Dict[str, int] | None = None) -> bytes:
    """
    Build canonical OML-C bytes:
      1) NFC strings
      2) Replace known keys/values with integer symbols (SFT)
      3) Deterministic CBOR (canonical=True)
    """
    sft = sft or get_default_sft()
    norm = _nfc(payload)
    symd = _apply_symbols(norm, sft)
    return cbor2.dumps(symd, canonical=True)


def from_oml_c(b: bytes) -> Any:
    """Decode CBOR back to Python types (no reverse-symbolization; consumers should know SFT)."""
    return cbor2.loads(b)


def compute_cid(b: bytes) -> str:
    """
    Compute content ID:
      multihash: blake3-256      => 0x1f + 32-byte digest
      multibase: base32 (lower)  => 'b' + base32lower
    """
    dig = blake3(b).digest(length=32)
    mh = bytes([0x1f, 32]) + dig  # 0x1f=blake3, 0x20=32 bytes
    b32 = base64.b32encode(mh).decode("ascii").lower().rstrip("=")
    return "b" + b32


# Optional tiny transport frame (OML-T) with QoS dict.
def to_oml_t(oml_c_bytes: bytes, qos: Dict[str, int | float | str] | None = None) -> bytes:
    frame = {"c": oml_c_bytes, "q": qos or {}}
    return cbor2.dumps(frame, canonical=True)


def from_oml_t(b: bytes) -> Tuple[bytes, Dict[str, Any]]:
    obj = cbor2.loads(b)
    return obj["c"], obj.get("q", {})
