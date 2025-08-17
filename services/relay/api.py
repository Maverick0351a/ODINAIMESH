from __future__ import annotations

import ipaddress
import json
import os
import time
from typing import Dict

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, AnyHttpUrl

from libs.odin_core.odin.ope import verify_over_content

app = FastAPI(title="ODIN Relay", version="0.0.2")

# --- SSRF defense helpers ---
PRIVATE_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_private_host(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
        return any(ip in net for net in PRIVATE_NETS)
    except ValueError:
        # not an IP; do not allow plain hostnames in this stub
        return True


# --- Header policy ---
ALLOWED_FWD_HEADERS = {"x-odin-oml-cid", "x-odin-ope", "x-odin-ope-kid"}

# Simple global rate limiter (QPS) using token bucket
_rl_last_ts = 0.0
_rl_tokens = 0.0


def _rate_limited() -> bool:
    global _rl_last_ts, _rl_tokens
    qps_env = os.getenv("ODIN_RELAY_RATE_LIMIT_QPS")
    if qps_env is None:
        return False  # disabled
    try:
        qps = float(qps_env)
    except Exception:
        qps = 1.0
    if qps <= 0:
        return True
    now = time.perf_counter()
    if _rl_last_ts == 0.0:
        _rl_last_ts = now
        _rl_tokens = qps
    # Refill tokens
    elapsed = now - _rl_last_ts
    _rl_tokens = min(qps, _rl_tokens + elapsed * qps)
    _rl_last_ts = now
    if _rl_tokens >= 1.0:
        _rl_tokens -= 1.0
        return False
    return True


class RelayIn(BaseModel):
    url: AnyHttpUrl
    method: str = "POST"
    headers: Dict[str, str] = {}
    bytes_b64: str


@app.post("/relay")
async def relay(req: RelayIn):
    target = req.url
    allow_private = os.getenv("ODIN_RELAY_ALLOW_PRIVATE") == "1"
    if _is_private_host(target.host) and not allow_private:
        raise HTTPException(status_code=400, detail="blocked private host")

    # rate limit
    if _rate_limited():
        raise HTTPException(status_code=429, detail="rate_limited")

    # Filter headers
    fwd_headers = {k: v for k, v in req.headers.items() if k.lower() in ALLOWED_FWD_HEADERS}

    # Verify OPE if supplied
    ope_b64 = fwd_headers.get("x-odin-ope")
    cid = fwd_headers.get("x-odin-oml-cid")
    body = None
    try:
        from base64 import b64decode

        body = b64decode(req.bytes_b64 + "==")
    except Exception:
        raise HTTPException(status_code=400, detail="invalid bytes_b64")

    if ope_b64:
        try:
            import base64

            ope = json.loads(base64.b64decode(ope_b64).decode("utf-8"))
            vr = verify_over_content(ope, body, expected_oml_cid=cid)
            if not vr.get("ok"):
                raise HTTPException(status_code=400, detail=f"ope_verify_failed:{vr.get('reason')}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"invalid_ope:{e}")

    timeout = httpx.Timeout(10.0, connect=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.request(req.method.upper(), str(target), content=body, headers=fwd_headers)
            return {
                "status": r.status_code,
                "headers": dict(r.headers),
                "len": len(r.content),
            }
    except httpx.RequestError as e:
        # Map network errors to 502
        raise HTTPException(status_code=502, detail=f"connect_error:{type(e).__name__}")
