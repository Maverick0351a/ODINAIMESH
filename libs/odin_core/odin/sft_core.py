from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import cbor2

# Core ODIN utilities (repo-local import paths)
from libs.odin_core.odin.cid import compute_cid  # OML-C CID over bytes

SFT_DIR = Path(__file__).parent
CORE_FILE = SFT_DIR / "core_v0_1.json"
CORE_ID = "core@v0.1"


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _json_sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_sft(sft_id: str = CORE_ID) -> Dict[str, Any]:
    if sft_id != CORE_ID:
        raise ValueError(f"unknown SFT id: {sft_id}")
    with CORE_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def sft_info(sft_id: str = CORE_ID) -> Dict[str, Any]:
    sft = load_sft(sft_id)
    # Compute stable JSON hash (for human-friendly debugging)
    json_bytes = _canonical_json_bytes(sft)
    json_sha256 = _json_sha256_hex(json_bytes)
    # Compute CID from canonical CBOR of the SFT object
    oml_c_bytes = cbor2.dumps(sft, canonical=True)
    cid = compute_cid(oml_c_bytes)
    return {"id": sft_id, "cid": cid, "json_sha256": json_sha256, "sft": sft}


@dataclass
class ValidationError:
    path: str
    error: str

    def as_dict(self) -> Dict[str, str]:
        return {"path": self.path, "error": self.error}


@dataclass
class ValidationResult:
    ok: bool
    errors: List[ValidationError]

    @property
    def error_dicts(self) -> List[Dict[str, str]]:
        return [e.as_dict() for e in self.errors]


_ALLOWED_INTENTS = {"echo", "translate", "transfer", "notify", "query"}


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def validate(obj: Any, sft_id: str = CORE_ID) -> ValidationResult:
    """Minimal, deterministic validation against core@v0.1.

    Rules:
      - Object required
      - 'intent': required string, must be in allowed set
      - 'amount': if present, must be a number
      - 'units': if present, must be a string
      - 'ts': if present, must be int or string
      - Others are permissive ('actor','subject','resource','action','reason')
    """
    errs: List[ValidationError] = []

    if sft_id != CORE_ID:
        return ValidationResult(ok=False, errors=[ValidationError(path="/", error=f"unsupported sft_id: {sft_id}")])

    if not isinstance(obj, dict):
        return ValidationResult(ok=False, errors=[ValidationError(path="/", error="expected object")])

    # intent
    if "intent" not in obj:
        errs.append(ValidationError(path="/intent", error="required"))
    else:
        if not isinstance(obj["intent"], str) or not obj["intent"].strip():
            errs.append(ValidationError(path="/intent", error="expected non-empty string"))
        elif obj["intent"] not in _ALLOWED_INTENTS:
            errs.append(ValidationError(path="/intent", error=f"unsupported intent '{obj['intent']}'"))

    # amount
    if "amount" in obj and not _is_number(obj["amount"]):
        errs.append(ValidationError(path="/amount", error="expected number"))

    # units
    if "units" in obj and not isinstance(obj["units"], str):
        errs.append(ValidationError(path="/units", error="expected string"))

    # ts
    if "ts" in obj and not (isinstance(obj["ts"], int) or isinstance(obj["ts"], str)):
        errs.append(ValidationError(path="/ts", error="expected integer or string"))

    return ValidationResult(ok=len(errs) == 0, errors=errs)
