from __future__ import annotations

import json
import os
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

ENV_SFT_MAPS_DIR = "ODIN_SFT_MAPS_DIR"
# Allow only simple basenames to prevent traversal
_ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._@-")


def _maps_dir() -> Path:
    return Path(os.getenv(ENV_SFT_MAPS_DIR, "config/sft_maps"))


def _is_safe_name(name: str) -> bool:
    return name.endswith(".json") and all(ch in _ALLOWED_CHARS for ch in name)


def _safe_path(basename: str) -> Path:
    base = _maps_dir().resolve()
    p = (base / basename).resolve()
    # Ensure the resolved path is inside the configured dir
    if not str(p).startswith(str(base)):
        raise HTTPException(
            status_code=400,
            detail={"error": "odin.sft_map.bad_name", "message": "invalid map path"},
        )
    return p


@router.get("/v1/sft/maps")
def list_maps() -> Dict[str, Any]:
    """
    Lists available SFT translation maps found under ODIN_SFT_MAPS_DIR (default: config/sft_maps).
    Returns: { count, maps: [{ name, from, to, size, sha256 }] }
    Invalid/Unreadable JSON files are skipped instead of failing the whole listing.
    """
    d = _maps_dir()
    items: List[Dict[str, Any]] = []

    if d.is_dir():
        for p in sorted(d.glob("*.json")):
            try:
                raw = p.read_bytes()
                data = json.loads(raw.decode("utf-8"))
                digest = sha256(raw).hexdigest()
            except Exception:
                # Ignore unreadable or invalid JSON
                continue

            items.append(
                {
                    "name": p.name,
                    "from": data.get("from_sft"),
                    "to": data.get("to_sft"),
                    "size": p.stat().st_size,
                    "sha256": digest,
                }
            )

    return {"count": len(items), "maps": items}


@router.get("/v1/sft/maps/{name:path}")
def get_map(name: str):
    """
    Fetch a single map by file name (basename with .json).
    Example: GET /v1/sft/maps/test_A@1__test_B@1.json
    Returns the JSON and sets ETag based on file content sha256 for caching.
    """
    if not _is_safe_name(name):
        raise HTTPException(
            status_code=400,
            detail={"error": "odin.sft_map.bad_name", "message": "invalid map name"},
        )

    path = _safe_path(name)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail={"error": "odin.sft_map.not_found", "message": name},
        )

    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
        digest = sha256(raw).hexdigest()
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail={"error": "odin.sft_map.invalid_json", "message": str(e)},
        )

    # Weak ETag is fine; content-addresses by sha256 to help clients cache
    return JSONResponse(content=data, headers={"ETag": f'W/"{digest}"'})
