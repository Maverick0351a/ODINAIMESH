from __future__ import annotations

import orjson
from typing import Any, Tuple


def canonical_json_bytes(obj: Any) -> bytes:
    """Return deterministic JSON bytes (sorted keys, newline-terminated).

    Uses orjson with sorted keys and a trailing newline for stable serialization.
    """
    return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS | orjson.OPT_APPEND_NEWLINE)


def try_parse_json(text: str) -> Tuple[Any | None, str | None]:
    """Parse JSON string, returning (obj, None) on success, or (None, error) on failure."""
    try:
        return orjson.loads(text), None
    except Exception as e:  # pragma: no cover - error path depends on orjson error messages
        return None, str(e)
