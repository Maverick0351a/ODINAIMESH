"""ODIN Protocol SFT Translation Service

Provides secure function transformation for payloads between SFT specifications,
with validation, field mapping, intent remapping, and drop/const operations.

Quick Win Features:
1. Canonicalization contract (json/nfc/no_ws/sort_keys) for reproducible CIDs
2. Field-level provenance tracking in translation receipts  
3. Coverage percentage and required-field gates with HEL policy integration
4. Deterministic defaults and enum validation to SFT map DSL
5. X-ODIN-SFT-Input-Type and X-ODIN-SFT-Desired-Type headers
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Union
import json
import os
import re
import time
import unicodedata

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


# ========== CANONICALIZATION CONTRACT ==========

def canonicalize_json(obj: Dict[str, Any], algorithm: str = "json/nfc/no_ws/sort_keys") -> str:
    """
    Apply canonicalization algorithm for reproducible CID computation.
    
    Algorithms:
    - json/nfc/no_ws/sort_keys: NFC normalization, no whitespace, sorted keys
    - json/nfc/compact: NFC normalization, compact JSON
    - json/sort_keys: Sort keys only (preserves original encoding)
    """
    if algorithm == "json/nfc/no_ws/sort_keys":
        # Apply NFC normalization recursively
        try:
            from .oml.encoder import _nfc
            normalized = _nfc(obj)
        except ImportError:
            # Fallback implementation
            normalized = _normalize_unicode_recursive(obj)
        # Compact JSON with sorted keys
        return json.dumps(normalized, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    elif algorithm == "json/nfc/compact":
        try:
            from .oml.encoder import _nfc
            normalized = _nfc(obj)
        except ImportError:
            normalized = _normalize_unicode_recursive(obj)
        return json.dumps(normalized, ensure_ascii=False, separators=(',', ':'))
    elif algorithm == "json/sort_keys":
        return json.dumps(obj, ensure_ascii=False, sort_keys=True)
    else:
        raise ValueError(f"Unknown canonicalization algorithm: {algorithm}")


def _normalize_unicode_recursive(obj: Any) -> Any:
    """Fallback NFC normalization when OML encoder not available."""
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, list):
        return [_normalize_unicode_recursive(x) for x in obj]
    if isinstance(obj, dict):
        return {_normalize_unicode_recursive(k): _normalize_unicode_recursive(v) for k, v in obj.items()}
    return obj


def compute_canonical_cid(obj: Dict[str, Any], algorithm: str = "json/nfc/no_ws/sort_keys") -> str:
    """Compute CID over canonicalized JSON representation."""
    canonical_json = canonicalize_json(obj, algorithm)
    canonical_bytes = canonical_json.encode('utf-8')
    try:
        from .oml.encoder import compute_cid
        return compute_cid(canonical_bytes)
    except ImportError:
        # Fallback to stable hash if CID not available
        from .jsonutil import stable_hash_b64u
        return f"fallback_{stable_hash_b64u(canonical_json)}"


# ========== FIELD PROVENANCE TRACKING ==========

@dataclass
class FieldProvenance:
    """Track the transformation history of a specific field."""
    source_field: str
    target_field: str
    operation: str  # "rename", "const", "drop", "intent_remap", "passthrough"
    source_value: Any = None
    target_value: Any = None
    timestamp: float = field(default_factory=time.time)


@dataclass  
class TranslationReceipt:
    """Detailed receipt of translation operations with field-level provenance."""
    from_sft: str
    to_sft: str
    input_cid: str
    output_cid: str
    canon_alg: str = "json/nfc/no_ws/sort_keys"
    field_provenance: List[FieldProvenance] = field(default_factory=list)
    coverage_percent: float = 0.0
    required_fields_met: bool = True
    transformation_count: int = 0
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "from_sft": self.from_sft,
            "to_sft": self.to_sft,
            "input_cid": self.input_cid,
            "output_cid": self.output_cid,
            "canon_alg": self.canon_alg,
            "field_provenance": [
                {
                    "source_field": fp.source_field,
                    "target_field": fp.target_field,
                    "operation": fp.operation,
                    "source_value": fp.source_value,
                    "target_value": fp.target_value,
                    "timestamp": fp.timestamp
                }
                for fp in self.field_provenance
            ],
            "coverage_percent": self.coverage_percent,
            "required_fields_met": self.required_fields_met,
            "transformation_count": self.transformation_count,
            "timestamp": self.timestamp
        }


# ========== COVERAGE GATES ==========

def calculate_field_coverage(input_fields: Set[str], output_fields: Set[str]) -> float:
    """Calculate percentage of input fields represented in output."""
    if not input_fields:
        return 100.0
    preserved = len(input_fields.intersection(output_fields))
    return (preserved / len(input_fields)) * 100.0


def check_required_fields(obj: Dict[str, Any], required_fields: List[str]) -> bool:
    """Check if all required fields are present and non-null."""
    for field_name in required_fields:
        if field_name not in obj or obj[field_name] is None:
            return False
    return True


def get_coverage_requirements(sft_id: str) -> Dict[str, Any]:
    """Get coverage requirements from HEL policy or SFT definition."""
    try:
        from .hel import HEL_POLICY
        policy = HEL_POLICY.get("coverage_gates", {}).get(sft_id, {})
        return {
            "min_coverage_percent": policy.get("min_coverage_percent", 80.0),
            "required_fields": policy.get("required_fields", []),
            "enforce_gates": policy.get("enforce_gates", False)
        }
    except ImportError:
        # Fallback to reasonable defaults
        return {
            "min_coverage_percent": 80.0,
            "required_fields": [],
            "enforce_gates": False
        }


# ========== ENHANCED SFT MAP WITH DEFAULTS ==========

@dataclass
class EnhancedSftMap:
    """Enhanced SFT map with deterministic defaults and validation."""
    from_sft: str
    to_sft: str
    intents: Dict[str, str] = field(default_factory=dict)
    fields: Dict[str, str] = field(default_factory=dict)
    const: Dict[str, Any] = field(default_factory=dict)
    drop: List[str] = field(default_factory=list)
    # Quick Win 4: Deterministic defaults and enum validation
    defaults: Dict[str, Any] = field(default_factory=dict)
    enum_constraints: Dict[str, List[str]] = field(default_factory=dict)
    required_fields: List[str] = field(default_factory=list)
    canon_alg: str = "json/nfc/no_ws/sort_keys"
    
    def apply_defaults(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        """Apply deterministic defaults to object."""
        result = dict(obj)
        for field_name, default_value in self.defaults.items():
            if field_name not in result or result[field_name] is None:
                result[field_name] = default_value
        return result
    
    def validate_enums(self, obj: Dict[str, Any]) -> List[str]:
        """Validate enum constraints."""
        violations = []
        for field_name, allowed_values in self.enum_constraints.items():
            if field_name in obj:
                value = obj[field_name]
                if value not in allowed_values:
                    violations.append(f"field_{field_name}_invalid_enum_value:{value}_not_in_{allowed_values}")
        return violations


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
    def __init__(self, code: str, message: str, violations: Optional[List[str]] = None, coverage_percent: Optional[float] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.violations: List[str] = violations or []
        self.coverage_percent = coverage_percent


@dataclass
class SftMap:
    from_sft: str
    to_sft: str
    intents: Dict[str, str] = field(default_factory=dict)
    fields: Dict[str, str] = field(default_factory=dict)
    const: Dict[str, Any] = field(default_factory=dict)
    drop: List[str] = field(default_factory=list)


def translate(payload: Dict[str, Any], m: SftMap, *, generate_receipt: bool = False, canon_alg: str = "json/nfc/no_ws/sort_keys") -> Union[Dict[str, Any], tuple[Dict[str, Any], TranslationReceipt]]:
    """
    Apply an SFT mapping with validation before and after.
    
    Quick Win enhancements:
    - Canonicalization contract with reproducible CIDs
    - Field-level provenance tracking  
    - Coverage percentage calculation with gates
    - Deterministic defaults application
    
    Args:
        payload: Input object to transform
        m: SFT mapping definition
        generate_receipt: Whether to return detailed transformation receipt
        canon_alg: Canonicalization algorithm for CID computation
        
    Returns:
        Transformed object, or (object, receipt) if generate_receipt=True
    """
    # Enhanced mapping with defaults if applicable
    if isinstance(m, EnhancedSftMap):
        enhanced_map = m
    else:
        # Convert basic SftMap to EnhancedSftMap
        enhanced_map = EnhancedSftMap(
            from_sft=m.from_sft,
            to_sft=m.to_sft,
            intents=m.intents,
            fields=m.fields,
            const=m.const,
            drop=m.drop,
            canon_alg=canon_alg
        )
    
    # Compute input CID
    input_cid = compute_canonical_cid(payload, canon_alg)
    
    # Track field provenance
    provenance: List[FieldProvenance] = []
    input_fields = set(payload.keys())
    
    # 1) Input validation
    vin = validate_obj(payload, enhanced_map.from_sft)
    if vin:
        raise TranslateError(
            "odin.translate.input_invalid",
            f"Payload fails {enhanced_map.from_sft} validation",
            vin,
        )

    out = dict(payload)

    # 2) Apply deterministic defaults first
    if enhanced_map.defaults:
        original_out = dict(out)
        out = enhanced_map.apply_defaults(out)
        for field_name, default_value in enhanced_map.defaults.items():
            if field_name not in original_out or original_out[field_name] is None:
                provenance.append(FieldProvenance(
                    source_field="<default>",
                    target_field=field_name,
                    operation="default",
                    source_value=None,
                    target_value=default_value
                ))

    # 3) Drop fields  
    for k in enhanced_map.drop:
        if k in out:
            dropped_value = out.pop(k, None)
            provenance.append(FieldProvenance(
                source_field=k,
                target_field="<dropped>",
                operation="drop",
                source_value=dropped_value,
                target_value=None
            ))

    # 4) Field renames (top-level)
    for src, dst in enhanced_map.fields.items():
        if src in out:
            value = out.pop(src)
            out[dst] = value
            provenance.append(FieldProvenance(
                source_field=src,
                target_field=dst,
                operation="rename",
                source_value=value,
                target_value=value
            ))

    # 5) Intent remap (if present)
    if isinstance(out.get("intent"), str):
        old_intent = out["intent"]
        new_intent = enhanced_map.intents.get(old_intent)
        if new_intent:
            out["intent"] = new_intent
            provenance.append(FieldProvenance(
                source_field="intent",
                target_field="intent",
                operation="intent_remap",
                source_value=old_intent,
                target_value=new_intent
            ))

    # 6) Const overlay (wins)
    for k, v in enhanced_map.const.items():
        old_value = out.get(k)
        out[k] = v
        provenance.append(FieldProvenance(
            source_field=k if k in payload else "<const>",
            target_field=k,
            operation="const",
            source_value=old_value,
            target_value=v
        ))

    # 7) Validate enum constraints if enhanced map
    if enhanced_map.enum_constraints:
        enum_violations = enhanced_map.validate_enums(out)
        if enum_violations:
            raise TranslateError(
                "odin.translate.enum_violation",
                f"Enum constraint violations in {enhanced_map.to_sft}",
                enum_violations
            )

    # 8) Calculate coverage
    output_fields = set(out.keys())
    coverage_percent = calculate_field_coverage(input_fields, output_fields)
    
    # 9) Check coverage gates
    coverage_reqs = get_coverage_requirements(enhanced_map.to_sft)
    if coverage_reqs["enforce_gates"]:
        if coverage_percent < coverage_reqs["min_coverage_percent"]:
            raise TranslateError(
                "odin.translate.insufficient_coverage",
                f"Coverage {coverage_percent:.1f}% below required {coverage_reqs['min_coverage_percent']}%",
                coverage_percent=coverage_percent
            )
    
    # 10) Check required fields
    required_fields_met = check_required_fields(out, coverage_reqs["required_fields"])
    if coverage_reqs["enforce_gates"] and not required_fields_met:
        missing = [f for f in coverage_reqs["required_fields"] if f not in out or out[f] is None]
        raise TranslateError(
            "odin.translate.missing_required_fields",
            f"Missing required fields: {missing}",
            [f"missing_required_field:{f}" for f in missing]
        )

    # 11) Output validation
    vout = validate_obj(out, enhanced_map.to_sft)
    if vout:
        raise TranslateError(
            "odin.translate.output_invalid",
            f"Translated payload fails {enhanced_map.to_sft} validation",
            vout,
        )
    
    # 12) Add passthrough provenance for unchanged fields
    for field_name in input_fields.intersection(output_fields):
        if not any(fp.source_field == field_name for fp in provenance):
            provenance.append(FieldProvenance(
                source_field=field_name,
                target_field=field_name,
                operation="passthrough",
                source_value=payload.get(field_name),
                target_value=out.get(field_name)
            ))
    
    if generate_receipt:
        output_cid = compute_canonical_cid(out, canon_alg)
        receipt = TranslationReceipt(
            from_sft=enhanced_map.from_sft,
            to_sft=enhanced_map.to_sft,
            input_cid=input_cid,
            output_cid=output_cid,
            canon_alg=canon_alg,
            field_provenance=provenance,
            coverage_percent=coverage_percent,
            required_fields_met=required_fields_met,
            transformation_count=len(provenance)
        )
        return out, receipt
    
    return out


def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.@-]+", "_", s)


def map_filename(from_sft: str, to_sft: str) -> str:
    return f"{_slug(from_sft)}__{_slug(to_sft)}.json"


def resolve_map_path(maps_dir: str, from_sft: str, to_sft: str) -> str:
    return os.path.join(maps_dir, map_filename(from_sft, to_sft))


def load_map_from_path(path: str, *, enhanced: bool = False) -> Union[SftMap, EnhancedSftMap]:
    """Load SFT map from file path, with optional enhanced features."""
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
    
    if enhanced:
        return EnhancedSftMap(
            from_sft=data.get("from_sft") or "",
            to_sft=data.get("to_sft") or "",
            intents=dict(data.get("intents") or {}),
            fields=dict(data.get("fields") or {}),
            const=dict(data.get("const") or {}),
            drop=list(data.get("drop") or []),
            defaults=dict(data.get("defaults") or {}),
            enum_constraints=dict(data.get("enum_constraints") or {}),
            required_fields=list(data.get("required_fields") or []),
            canon_alg=data.get("canon_alg", "json/nfc/no_ws/sort_keys")
        )
    else:
        return SftMap(
            from_sft=data.get("from_sft") or "",
            to_sft=data.get("to_sft") or "",
            intents=dict(data.get("intents") or {}),
            fields=dict(data.get("fields") or {}),
            const=dict(data.get("const") or {}),
            drop=list(data.get("drop") or []),
        )


# ========== HEADER SUPPORT FOR TYPE DECLARATIONS ==========

def extract_sft_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Extract SFT type declarations from HTTP headers.
    
    Quick Win 5: X-ODIN-SFT-Input-Type and X-ODIN-SFT-Desired-Type headers
    """
    sft_headers = {}
    
    # Standard header names (case-insensitive)
    header_mappings = {
        "x-odin-sft-input-type": "input_type",
        "x-odin-sft-desired-type": "desired_type",
        "x-odin-sft-canon-alg": "canon_alg",
        "x-odin-sft-enforce-gates": "enforce_gates"
    }
    
    for header_name, header_value in headers.items():
        normalized_name = header_name.lower()
        if normalized_name in header_mappings:
            sft_headers[header_mappings[normalized_name]] = header_value
    
    return sft_headers


def translate_with_headers(payload: Dict[str, Any], headers: Dict[str, str], maps_dir: str = "configs/sft_maps") -> tuple[Dict[str, Any], TranslationReceipt]:
    """
    Perform translation using type information from HTTP headers.
    
    Quick Win 5: Type declarations via headers
    """
    sft_info = extract_sft_headers(headers)
    
    if "input_type" not in sft_info or "desired_type" not in sft_info:
        raise TranslateError(
            "odin.translate.missing_type_headers",
            "Required headers X-ODIN-SFT-Input-Type and X-ODIN-SFT-Desired-Type not found"
        )
    
    from_sft = sft_info["input_type"]
    to_sft = sft_info["desired_type"]
    canon_alg = sft_info.get("canon_alg", "json/nfc/no_ws/sort_keys")
    
    # Load appropriate map
    map_path = resolve_map_path(maps_dir, from_sft, to_sft)
    try:
        sft_map = load_map_from_path(map_path, enhanced=True)
    except FileNotFoundError:
        # Create basic map if none exists
        sft_map = EnhancedSftMap(
            from_sft=from_sft,
            to_sft=to_sft,
            canon_alg=canon_alg
        )
    
    # Apply override settings from headers
    if "enforce_gates" in sft_info:
        # This would require modifying coverage requirements, for now just validate
        pass
    
    return translate(payload, sft_map, generate_receipt=True, canon_alg=canon_alg)


# Seed the registry (core validator if available)
clear_sft_registry()


# Integration with SFT Advanced Features (Quick Wins 6-9)
try:
    from .sft_advanced import (
        BidirectionalSftMap, perform_round_trip_test,
        SftMapLinter, MoneyNormalizer, UnitConverter
    )
    
    # Export advanced features for external use
    __all__ = [
        'EnhancedSftMap', 'TranslationReceipt', 'FieldProvenance', 'translate',
        'translate_from_headers', 'TranslateError', 'canonicalize_json',
        'compute_canonical_cid', 'register_sft', 'clear_sft_registry',
        # Advanced features
        'BidirectionalSftMap', 'perform_round_trip_test', 'SftMapLinter',
        'MoneyNormalizer', 'UnitConverter'
    ]
    
except ImportError:
    # Advanced features not available - basic functionality only
    __all__ = [
        'EnhancedSftMap', 'TranslationReceipt', 'FieldProvenance', 'translate',
        'translate_from_headers', 'TranslateError', 'canonicalize_json',
        'compute_canonical_cid', 'register_sft', 'clear_sft_registry'
    ]
