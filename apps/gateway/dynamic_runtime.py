from __future__ import annotations

import os
from typing import Optional, Dict, Any


_RELOADER = None


def _enabled() -> bool:
    return os.getenv("ODIN_DYNAMIC_ENABLE", "0") in ("1", "true", "True")


def get_reloader():
    global _RELOADER
    if not _enabled():
        return None
    if _RELOADER is None:
        try:
            from libs.odin_core.odin.dynamic_reload import make_reloader  # type: ignore

            _RELOADER = make_reloader()
        except Exception:
            _RELOADER = None
    return _RELOADER


def dynamic_status() -> Optional[Dict[str, Any]]:
    r = get_reloader()
    if r is None:
        return None
    try:
        return r.status()
    except Exception:
        return None


def dynamic_force_reload(target: str = "all") -> Optional[Dict[str, Any]]:
    r = get_reloader()
    if r is None:
        return None
    try:
        return r.force_reload(target)
    except Exception:
        return None
