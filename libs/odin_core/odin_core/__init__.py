"""
Compatibility shim package so imports like `from odin_core.odin...` work.

This package aliases `odin_core.odin` to the top-level `odin` package that
is provided by this distribution. This keeps existing imports working while
the canonical import path is `odin`.
"""
from __future__ import annotations

import importlib
import sys

# Alias the top-level 'odin' package under 'odin_core.odin'
try:
    _odin = importlib.import_module("odin")
    sys.modules[__name__ + ".odin"] = _odin
except Exception:  # pragma: no cover - best-effort shim
    pass

__all__ = ["odin"]
