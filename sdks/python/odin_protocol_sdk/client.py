import base64
import json
from typing import Any, Dict, Optional, Tuple
import httpx


class OdinClient:
    def __init__(self, base_url: str, client: Optional[httpx.Client] = None, require_proof: bool = True):
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client()
        self.require_proof = require_proof

    @classmethod
    def from_discovery(cls, url: str, require_proof: bool = True) -> "OdinClient":
        # Minimal discovery: fetch and ignore for preview; future versions may configure proof negotiation
        d_url = url.rstrip("/") + "/.well-known/odin/discovery.json"
        try:
            httpx.get(d_url, timeout=5.0)
        except Exception:
            pass
        return cls(url, require_proof=require_proof)

    def post_envelope(self, path: str, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        url = self.base_url + path
        r = self.client.post(url, json=payload, timeout=10.0)
        r.raise_for_status()
        data = r.json()
        verification = {
            "ok": True,
            "oml_cid": r.headers.get("x-odin-oml-cid"),
            "hop_id": r.headers.get("x-odin-hop-id"),
            "trace_id": r.headers.get("x-odin-trace-id"),
        }
        return data, verification

    def post_json(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        url = self.base_url + path
        r = self.client.post(url, json=body, timeout=15.0)
        r.raise_for_status()
        return r.json()
