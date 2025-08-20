"""
Redaction utilities for masking sensitive fields in nested JSON-like objects.

Pattern syntax:
- Dot-separated path segments, e.g., "user.email" or "items.*.secret".
- "*" matches any single segment. When walking lists, the walker uses "*" for the index segment.

Examples:
- apply_redactions({"password": "p"}, ["password"]) => {"password": "***"}
- apply_redactions({"user": {"email": "e"}}, ["user.email"]) => mask email
- apply_redactions({"items": [{"secret": 1}, {"secret": 2}]}, ["items.*.secret"]) => mask both secrets
"""
from typing import Any, Iterable, List

Mask = str


def _split(p: str) -> List[str]:
    return [seg for seg in p.split(".") if seg]


def _match(path: List[str], pattern: List[str]) -> bool:
    if len(path) < len(pattern):
        return False
    for i, seg in enumerate(pattern):
        if seg == "*":
            continue
        if path[i] != seg:
            return False
    return True


def apply_redactions(obj: Any, patterns: Iterable[str], mask: Mask = "***") -> Any:
    pats = [_split(p) for p in patterns]

    def _walk(node: Any, path: List[str]) -> Any:
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                newp = path + [k]
                # Only redact when the pattern length exactly equals the current path length
                if any(_match(newp, pat) and len(newp) == len(pat) for pat in pats):
                    out[k] = mask
                else:
                    out[k] = _walk(v, newp)
            return out
        elif isinstance(node, list):
            # Represent list index position with a wildcard segment for matching
            return [_walk(v, path + ["*"]) for v in node]
        else:
            return node

    return _walk(obj, [])
