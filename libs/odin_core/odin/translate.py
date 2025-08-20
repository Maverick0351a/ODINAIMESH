from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import json
import os
import re

# A validator returns one of:
# - [] or None (means OK)
# - bool (True=OK, False=invalid)
# - (bool, [errors]) tuple
# - {"ok": bool, "errors" or "violations": [...]}
Validator = Callable[[Dict[str, Any]], Any]

_SFT_VALIDATORS: Dict[str, Validator] = {}


def register_sft(sft_id: str, validator: Validator) -> None:
    """Register/override a validator for an SFT id."""
    _SFT_VALIDATORS[sft_id] = validator


def clear_sft_registry() -> None:
    """Reset registry to defaults (re-seeds core if available)."""
    _SFT_VALIDATORS.clear()
    try:
        # Prefer relative import to avoid path ambiguities.
        from .sft import CORE_ID, validate as _core_validate  # type: ignore
        _SFT_VALIDATORS[CORE_ID] = _core_validate
    except Exception:
        # No core validator available is acceptable; validation becomes permissive.
        pass
    # Optionally seed alpha@v1 if available
    try:
        from .sft_alpha import ID as _ALPHA_ID, validate as _alpha_validate  # type: ignore
        _SFT_VALIDATORS[_ALPHA_ID] = _alpha_validate
    except Exception:
        pass
    # Optionally seed beta@v1 if available
    try:
        from .sft_beta import ID as _BETA_ID, validate as _beta_validate  # type: ignore
        _SFT_VALIDATORS[_BETA_ID] = _beta_validate
    except Exception:
        pass
    # Optionally seed odin.task@v1 and openai.tool@v1 if available
    try:
        from .sft_tools import (
            ODIN_TASK_ID as _TASK_ID,
            OPENAI_TOOL_ID as _TOOL_ID,
            validate_odin_task as _v_task,
            validate_openai_tool as _v_tool,
        )  # type: ignore
        _SFT_VALIDATORS[_TASK_ID] = _v_task
        _SFT_VALIDATORS[_TOOL_ID] = _v_tool
    except Exception:
        pass


def get_validator(sft_id: str) -> Optional[Validator]:
    return _SFT_VALIDATORS.get(sft_id)


def _norm_validation_result(res: Any) -> List[str]:
    if res is None:
        return []
    if isinstance(res, bool):
        return [] if res else ["invalid"]
    if isinstance(res, list):
        return res
    if isinstance(res, tuple):
        if not res:
            return []
        ok = bool(res[0])
        if ok:
            return []
        if len(res) > 1 and isinstance(res[1], list):
            return res[1]
        return ["invalid"]
    if isinstance(res, dict):
        ok = res.get("ok", True)
        if ok:
            return []
        errs = res.get("errors") or res.get("violations") or []
        return errs if isinstance(errs, list) else ["invalid"]
    # Unknown truthiness; treat truthy as OK.
    return [] if res else ["invalid"]


def validate_obj(obj: Dict[str, Any], sft_id: str) -> List[str]:
    v = get_validator(sft_id)
    if not v:
        return []  # permissive when unknown
    try:
        res = v(obj)
    except Exception as e:  # keep validators from crashing the pipeline
        return [f"validator_exception:{type(e).__name__}:{e}"]
    return _norm_validation_result(res)


class TranslateError(Exception):
    def __init__(self, code: str, message: str, violations: Optional[List[str]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.violations: List[str] = violations or []


@dataclass
class SftMap:
    from_sft: str
    to_sft: str
    intents: Dict[str, str] = field(default_factory=dict)
    fields: Dict[str, str] = field(default_factory=dict)
    const: Dict[str, Any] = field(default_factory=dict)
    drop: List[str] = field(default_factory=list)


def translate(payload: Dict[str, Any], m: SftMap) -> Dict[str, Any]:
    """Apply an SFT mapping with validation before and after."""
    vin = validate_obj(payload, m.from_sft)
    if vin:
        raise TranslateError(
            "odin.translate.input_invalid",
            f"Payload fails {m.from_sft} validation",
            vin,
        )

    out = dict(payload)

    # 1) Drop first
    for k in m.drop:
        out.pop(k, None)

    # 2) Field renames (top-level)
    for src, dst in m.fields.items():
        if src in out:
            out[dst] = out.pop(src)

    # 3) Intent remap (if present)
    if isinstance(out.get("intent"), str):
        new_int = m.intents.get(out["intent"])
        if new_int:
            out["intent"] = new_int

    # 4) Const overlay (wins)
    for k, v in m.const.items():
        out[k] = v

    vout = validate_obj(out, m.to_sft)
    if vout:
        raise TranslateError(
            "odin.translate.output_invalid",
            f"Translated payload fails {m.to_sft} validation",
            vout,
        )
    return out


def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.@-]+", "_", s)


def map_filename(from_sft: str, to_sft: str) -> str:
    return f"{_slug(from_sft)}__{_slug(to_sft)}.json"


def resolve_map_path(maps_dir: str, from_sft: str, to_sft: str) -> str:
    return os.path.join(maps_dir, map_filename(from_sft, to_sft))


def load_map_from_path(path: str) -> SftMap:
    # Support loading from Google Cloud Storage when path uses gcs:// or gs://
    if path.startswith("gcs://") or path.startswith("gs://"):
        # Format: gcs://bucket/key... or gs://bucket/key...
        scheme, _, rest = path.partition("://")
        bucket, _, key = rest.partition("/")
        if not bucket or not key:
            raise TranslateError("odin.translate.map_not_found", f"invalid_gcs_path:{path}")
        try:
            from .storage import GcsStorage  # optional dependency path

            data_bytes = GcsStorage(bucket=bucket).get_bytes(key)
            data = json.loads(data_bytes.decode("utf-8"))
        except Exception as e:
            raise TranslateError("odin.translate.map_not_found", f"gcs_error:{type(e).__name__}:{e}")
    else:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    return SftMap(
        from_sft=data.get("from_sft") or "",
        to_sft=data.get("to_sft") or "",
        intents=dict(data.get("intents") or {}),
        fields=dict(data.get("fields") or {}),
        const=dict(data.get("const") or {}),
        drop=list(data.get("drop") or []),
    )


# Seed the registry (core validator if available)
clear_sft_registry()
