import base64
import json
from blake3 import blake3


def _canonical_json_bytes(obj) -> bytes:
    # Deterministic JSON (sorted keys, no whitespace) + newline for stability
    return (json.dumps(obj, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def compute_cid(obj) -> str:
    """Compute a BLAKE3-256 base32-lower CID over canonical JSON bytes.
    This mirrors the OML-CID approach used by the gateway.
    """
    data = _canonical_json_bytes(obj)
    h = blake3(data).digest()
    # base32 lower, no padding
    import base64 as _b64
    cid = _b64.b32encode(h).decode("ascii").lower().rstrip("=")
    return cid
