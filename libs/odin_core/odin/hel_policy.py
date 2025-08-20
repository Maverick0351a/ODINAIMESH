from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

Number = Union[int, float]


@dataclass
class Violation:
    code: str
    message: str
    path: str = "/"

    def as_dict(self) -> Dict[str, str]:
        out = {"code": self.code, "message": self.message}
        if self.path:
            out["path"] = self.path
        return out


@dataclass
class PolicyResult:
    allowed: bool
    violations: List[Violation]

    # Back-compat: allow tuple-unpack like (ok, violations)
    def __iter__(self):  # type: ignore[override]
        yield self.allowed
        yield [v.message for v in self.violations]

    def to_tuple(self):
        return (self.allowed, [v.message for v in self.violations])


def load_policy(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _match_intent(intent: Optional[str], patterns: List[str]) -> bool:
    if not intent:
        return False
    for pat in patterns:
        if fnmatch.fnmatch(intent, pat):
            return True
    return False


def _get_at_path(obj: Any, pointer: str) -> Any:
    """
    Minimal JSON-Pointer-like accessor.
    Accepts "/a/b" or "a.b". Returns None if path not found.
    """
    if not pointer or pointer == "/":
        return obj
    parts: List[str]
    if pointer.startswith("/"):
        parts = [p for p in pointer.split("/")[1:] if p]
    else:
        parts = [p for p in pointer.split(".") if p]
    cur = obj
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return None
    return cur


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _json_ptr_join(base: str, key: str | int) -> str:
    if not base or base == "/":
        return f"/{key}"
    return f"{base}/{key}"


def _iter_intents(obj: Any, base_path: str = "/") -> List[tuple[str, str, Dict[str, Any]]]:
    """Collect (path, intent, node) for every dict in the object graph that
    contains a string 'intent'. Path uses a JSON-Pointer-like format.
    """
    found: List[tuple[str, str, Dict[str, Any]]] = []

    def walk(x: Any, p: str) -> None:
        if isinstance(x, dict):
            v = x.get("intent")
            if isinstance(v, str):
                found.append((p, v, x))
            for k, vv in x.items():
                walk(vv, _json_ptr_join(p, k))
        elif isinstance(x, list):
            for i, it in enumerate(x):
                walk(it, _json_ptr_join(p, i))

    walk(obj, base_path)
    return found


def evaluate_policy(
    payload: Dict[str, Any],
    policy: Dict[str, Any],
) -> PolicyResult:
    """
    Evaluate content-aware HEL policy against a normalized payload.

    Policy JSON supported fields:
      - allow_kids: [kid...]
      - deny_kids: [kid...]
      - allowed_jwks_hosts: ["example.com", "*.odin.local", ...]
      - allow_intents: ["echo","translate","transfer","query","notify","delete","execute", ...] (glob supported)
      - deny_intents:  same shape (glob supported)
      - require_reason_for_intents: ["delete","execute"]
      - field_constraints: [
          {"when_intent":"transfer","path":"/amount","op":"<=","value":1000},
          {"when_intent":"notify","path":"/reason","op":"present"}
        ]
    NOTE: allow/deny KID & JWKS host checks are evaluated in middleware; this function evaluates content only.
    """
    # Back-compat: tolerate swapped args where callers pass (policy, payload)
    def _looks_like_policy(x: Any) -> bool:
        return isinstance(x, dict) and any(
            k in x for k in ("allow_intents", "deny_intents", "require_reason_for", "require_reason_for_intents", "field_constraints")
        )

    def _looks_like_payload(x: Any) -> bool:
        return isinstance(x, dict) and ("intent" in x or "payload" in x)

    if _looks_like_policy(payload) and _looks_like_payload(policy):
        payload, policy = policy, payload  # swap

    violations: List[Violation] = []
    intent = payload.get("intent")
    intents = _iter_intents(payload)  # list of (path, intent, node)

    allow_intents = list(policy.get("allow_intents", []) or [])
    deny_intents = list(policy.get("deny_intents", []) or [])
    # Support alias: require_reason_for (synonym of require_reason_for_intents)
    require_reason_for_intents = list(
        (policy.get("require_reason_for_intents")
         or policy.get("require_reason_for")
         or [])
        or []
    )

    # Normalize field_constraints: accept list of rule objects (existing) OR
    # a dict shorthand like {"reason": {"min_len": 3, "present": true}}
    fc_raw = policy.get("field_constraints", [])
    field_constraints: List[Dict[str, Any]] = []
    if isinstance(fc_raw, list):
        field_constraints = list(fc_raw)
    elif isinstance(fc_raw, dict):
        for field, constraints in fc_raw.items():
            if not isinstance(constraints, dict):
                continue
            path = field if field.startswith("/") else f"/{field}"
            # present/absent booleans
            if "present" in constraints:
                want = bool(constraints.get("present"))
                field_constraints.append({"path": path, "op": "present" if want else "absent"})
            if "absent" in constraints:
                want_absent = bool(constraints.get("absent"))
                if want_absent:
                    field_constraints.append({"path": path, "op": "absent"})
            # min_len / max_len for strings or arrays
            if "min_len" in constraints:
                try:
                    v = int(constraints.get("min_len"))
                    field_constraints.append({"path": path, "op": "min_len", "value": v})
                except Exception:
                    pass
            if "max_len" in constraints:
                try:
                    v = int(constraints.get("max_len"))
                    field_constraints.append({"path": path, "op": "max_len", "value": v})
                except Exception:
                    pass
            # equals / not_equals
            if "equals" in constraints:
                field_constraints.append({"path": path, "op": "==", "value": constraints.get("equals")})
            if "not_equals" in constraints:
                field_constraints.append({"path": path, "op": "!=", "value": constraints.get("not_equals")})

    # Deny list (highest precedence)
    if deny_intents:
        for path, it, _node in intents:
            if _match_intent(it, deny_intents):
                # Point to the specific node's intent path
                violations.append(
                    Violation(code="intent.denied", message=f"intent '{it}' is denied", path=f"{path}/intent")
                )

    # Allow list (if present)
    if allow_intents:
        for path, it, _node in intents:
            if not _match_intent(it, allow_intents):
                violations.append(
                    Violation(code="intent.not_allowed", message=f"intent '{it}' not in allowlist", path=f"{path}/intent")
                )

    # Require reason for specified intents
    if require_reason_for_intents:
        for path, it, node in intents:
            if _match_intent(it, require_reason_for_intents):
                # Accept either 'reason' or 'why' as justification fields
                reason = node.get("reason")
                why = node.get("why")
                has_reason = isinstance(reason, str) and reason.strip()
                has_why = isinstance(why, str) and why.strip()
                if not (has_reason or has_why):
                    violations.append(
                        Violation(
                            code="reason.required",
                            message="reason/why required for this intent",
                            path=f"{path}/reason",
                        )
                    )

    # Field constraints
    for rule in field_constraints:
        when_intent = rule.get("when_intent")
        if when_intent and not _match_intent(intent, [when_intent]):
            continue
        path = rule.get("path", "/")
        op = (rule.get("op") or "").strip()
        want = rule.get("value", None)
        got = _get_at_path(payload, path)

        if op in ("present", "absent"):
            present = got is not None and not (isinstance(got, str) and got == "")
            if op == "present" and not present:
                violations.append(Violation(code="field.missing", message=f"field required at {path}", path=path))
            if op == "absent" and present:
                violations.append(Violation(code="field.forbidden", message=f"field forbidden at {path}", path=path))
            continue

        # Length comparators for strings/lists
        if op in ("min_len", "max_len"):
            if got is None:
                violations.append(Violation(code="field.missing", message=f"field required at {path}", path=path))
                continue
            if not isinstance(got, (str, list)):
                violations.append(Violation(code="type.mismatch", message=f"expected string or list at {path}", path=path))
                continue
            try:
                n = int(want)
            except Exception:
                violations.append(Violation(code="constraint.bad_value", message=f"invalid value for {op} at {path}", path=path))
                continue
            ln = len(got)
            ok = (ln >= n) if op == "min_len" else (ln <= n)
            if not ok:
                cmp = ">=" if op == "min_len" else "<="
                violations.append(Violation(code="constraint.failed", message=f"len({path}) {cmp} {n} failed (got {ln})", path=path))
            continue

        # Numeric comparators
        if op in ("<", "<=", ">", ">=", "==", "!="):
            if isinstance(want, (int, float)) and not _is_number(got):
                violations.append(Violation(code="type.mismatch", message=f"expected number at {path}", path=path))
                continue
            # string equality is allowed for == / !=
            if op in ("==", "!="):
                ok = (got == want) if op == "==" else (got != want)
            else:
                # order comparisons require numbers
                if not (_is_number(got) and _is_number(want)):
                    violations.append(Violation(code="type.mismatch", message=f"expected number at {path}", path=path))
                    continue
                if op == "<":
                    ok = got < want
                elif op == "<=":
                    ok = got <= want
                elif op == ">":
                    ok = got > want
                else:
                    ok = got >= want
            if not ok:
                violations.append(Violation(code="constraint.failed", message=f"{path} {op} {want} failed (got {got})", path=path))
            continue

        # Unknown operator
        if op:
            violations.append(Violation(code="constraint.unknown_op", message=f"unknown op '{op}' at {path}", path=path))

    return PolicyResult(allowed=(len(violations) == 0), violations=violations)
