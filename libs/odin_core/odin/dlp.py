from __future__ import annotations

import re
from typing import Any


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CC_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def _mask_str(s: str) -> str:
    s = _EMAIL_RE.sub("***@***", s)
    s = _SSN_RE.sub("***-**-****", s)
    s = _CC_RE.sub("**** **** **** ****", s)
    return s


def apply_simple_dlp(obj: Any) -> Any:
    """Shallow recursive masking for common PII patterns in strings.

    Not a substitute for enterprise DLP; used to prevent accidental leaks in stored receipts.
    """
    if isinstance(obj, str):
        return _mask_str(obj)
    if isinstance(obj, list):
        return [apply_simple_dlp(x) for x in obj]
    if isinstance(obj, dict):
        return {k: apply_simple_dlp(v) for k, v in obj.items()}
    return obj
