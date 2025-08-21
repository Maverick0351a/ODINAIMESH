from __future__ import annotations

import glob
import hashlib
import json
import os
import threading
from typing import Any, Dict, Optional, Tuple

from fastapi import FastAPI

# SFT registry APIs
from libs.odin_core.odin.translate import (
    clear_sft_registry,
    load_map_from_path,
    register_sft,
)

# Built-in SFT validators (core + reference alpha/beta)
try:
    from libs.odin_core.odin.sft_core import CORE_ID, validate as validate_core  # type: ignore
except Exception:  # pragma: no cover
    CORE_ID, validate_core = "core@v0.1", lambda obj: (True, [])

try:
    from libs.odin_core.odin.sft_alpha import ALPHA_ID, validate as validate_alpha  # type: ignore
except Exception:  # pragma: no cover
    ALPHA_ID, validate_alpha = "alpha@v1", lambda obj: (True, [])

try:
    from libs.odin_core.odin.sft_beta import BETA_ID, validate as validate_beta  # type: ignore
except Exception:  # pragma: no cover
    BETA_ID, validate_beta = "beta@v1", lambda obj: (True, [])


_lock = threading.Lock()
_policy_cache: Dict[str, Any] = {}
_policy_version: Optional[str] = None

_maps_count: int = 0
_maps_hash: Optional[str] = None


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")


def _read_policy_from_env() -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Load HEL policy from either:
      - ODIN_HEL_POLICY_JSON (inline JSON string), or
      - ODIN_HEL_POLICY_PATH (filesystem path)
    Returns (policy_dict, version_hex).
    """
    inline = os.getenv("ODIN_HEL_POLICY_JSON")
    if inline:
        try:
            policy = json.loads(inline)
            return policy, _sha256_bytes(_canonical_json(policy))
        except Exception as e:
            raise ValueError(f"ODIN_HEL_POLICY_JSON invalid: {e}") from e

    path = os.getenv("ODIN_HEL_POLICY_PATH")
    if path:
        with open(path, "rb") as f:
            raw = f.read()
        try:
            policy = json.loads(raw.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"ODIN_HEL_POLICY_PATH JSON parse error: {e}") from e
        return policy, _sha256_bytes(raw)

    # No policy configured — treat as permissive empty policy.
    return {}, None


def get_hel_policy() -> Dict[str, Any]:
    """Thread-safe getter used by middleware/handlers."""
    global _policy_cache
    with _lock:
        # Optional dynamic reloader path (TTL-based passive reload)
        try:
            from apps.gateway.dynamic_runtime import get_reloader  # type: ignore

            r = get_reloader()
            if r is not None:
                try:
                    pol = r.get_policy() or {}
                    _policy_cache = pol
                    # Derive a local version hash for compatibility with existing status
                    try:
                        global _policy_version
                        _policy_version = _sha256_bytes(_canonical_json(pol)) if pol else None
                    except Exception:
                        pass
                    return _policy_cache
                except Exception:
                    # Fall through to env-based cache on any failure
                    pass
        except Exception:
            pass
        if not _policy_cache:
            # lazy init
            reload_policy()
        return _policy_cache


def reload_policy() -> Dict[str, Any]:
    """Force reload policy; returns status dict."""
    global _policy_cache, _policy_version
    policy, version = _read_policy_from_env()
    with _lock:
        _policy_cache = policy or {}
        _policy_version = version
        return {
            "ok": True,
            "policy_version": _policy_version,
            "has_policy": bool(_policy_cache),
        }


def _register_builtins():
    """Re-register built-in SFT validators after a registry clear."""
    register_sft(CORE_ID, validate_core)
    register_sft(ALPHA_ID, validate_alpha)
    register_sft(BETA_ID, validate_beta)


def _sft_maps_dir() -> str:
    return os.getenv("ODIN_SFT_MAPS_DIR", "config/sft_maps")


def reload_sft_maps() -> Dict[str, Any]:
    """Clear + (re)load all SFT maps from dir. Returns status dict."""
    global _maps_count, _maps_hash
    dir_path = _sft_maps_dir()
    patterns = [os.path.join(dir_path, "*.json")]

    with _lock:
        clear_sft_registry()
        _register_builtins()

        files = []
        for pat in patterns:
            files.extend(glob.glob(pat))

        combined_hash = hashlib.sha256()
        loaded = 0
        errors: Dict[str, str] = {}

        for p in sorted(files):
            try:
                load_map_from_path(p)
                loaded += 1
                with open(p, "rb") as f:
                    combined_hash.update(f.read())
            except Exception as e:  # be robust; skip bad files
                errors[os.path.basename(p)] = str(e)

        _maps_count = loaded
        _maps_hash = combined_hash.hexdigest() if loaded else None

        return {
            "ok": True,
            "count": _maps_count,
            "hash": _maps_hash,
            "errors": errors or None,
            "dir": dir_path,
        }


def wire_startup(app: FastAPI) -> None:
    """Call from app startup to pre-warm caches; optionally start watchers."""
    reload_policy()
    reload_sft_maps()

    # Optional file watchers for local dev
    if os.getenv("ODIN_WATCH_CONFIG", "0") in ("1", "true", "True"):
        try:
            import threading as _thr  # local name
            from watchfiles import awatch  # type: ignore
            import asyncio

            async def _watch_loop():
                policy_path = os.getenv("ODIN_HEL_POLICY_PATH")
                maps_dir = _sft_maps_dir()
                watch_targets = [t for t in [policy_path, maps_dir] if t]

                if not watch_targets:
                    return

                async for _changes in awatch(*watch_targets):
                    try:
                        reload_policy()
                    except Exception:
                        pass
                    try:
                        reload_sft_maps()
                    except Exception:
                        pass

            def _run():
                asyncio.run(_watch_loop())

            t = _thr.Thread(target=_run, daemon=True)
            t.start()
        except Exception:
            # watcher is optional; ignore if missing
            pass
