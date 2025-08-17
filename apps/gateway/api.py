from __future__ import annotations

from fastapi import FastAPI, Request, Response, HTTPException
from pydantic import BaseModel
import orjson
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
import time
from pathlib import Path
import os

# OML core
from libs.odin_core.odin.oml import to_oml_c, compute_cid, get_default_sft
from libs.odin_core.odin.ope import OpeKeypair, sign_over_content
from libs.odin_core.odin.security.keystore import (
    load_keypair_from_env,
    load_keystore_from_json_env,
    ensure_keystore_file,
)
from libs.odin_core.odin.jsonutil import canonical_json_bytes
import json
import base64
from functools import lru_cache


def _orjson_dumps(v, *, default):
    return orjson.dumps(v, default=default).decode()


app = FastAPI(title="ODIN Gateway", version="0.0.4")

# simple metrics
REG = CollectorRegistry(auto_describe=True)
REQS = Counter("odin_http_requests_total", "gateway requests", ["path", "method"], registry=REG)
LAT = Histogram("odin_http_request_seconds", "gateway latency", ["path", "method"], registry=REG)


@app.middleware("http")
async def metrics_mw(request: Request, call_next):
    start = time.perf_counter()
    try:
        resp = await call_next(request)
        return resp
    finally:
        LAT.labels(request.url.path, request.method).observe(time.perf_counter() - start)
        REQS.labels(request.url.path, request.method).inc()


@app.get("/health")
def health():
    return {"ok": True, "service": "gateway"}


@app.get("/metrics")
def metrics():
    return generate_latest(REG), 200, {"Content-Type": CONTENT_TYPE_LATEST}


class EchoIn(BaseModel):
    message: str


@app.post("/v1/echo")
def echo(body: EchoIn):
    return {"echo": body.message}


# ---- Minimal translate -> OML wiring ----
class TranslateIn(BaseModel):
    content: str
    source_lang: str | None = None
    target_lang: str = "en"


@lru_cache(maxsize=1)
def _get_signing_keypair() -> OpeKeypair:
    # Prefer persistent keystore under ODIN_KEYSTORE_PATH (or tmp/odin/keystore.json)
    ks_path = os.environ.get("ODIN_KEYSTORE_PATH") or os.path.join(
        os.environ.get("ODIN_TMP_DIR", "tmp/odin"), "keystore.json"
    )
    try:
        ks, active = ensure_keystore_file(ks_path)
        if active and active in ks:
            return ks[active]
        # fallback to deterministic first
        if ks:
            return sorted(ks.items(), key=lambda kv: kv[0])[0][1]
    except Exception:
        pass
    # env-only fallback
    loaded = load_keypair_from_env()
    if loaded is not None:
        return loaded.keypair
    # JSON env fallback
    ks = load_keystore_from_json_env() or {}
    if ks:
        return sorted(ks.items(), key=lambda kv: kv[0])[0][1]
    # ephemeral last resort
    return OpeKeypair.generate("ephemeral")


@app.post("/v1/translate")
def translate(body: TranslateIn, request: Request, response: Response):
    # Build a tiny canonical OML graph for translation intent
    sft = get_default_sft()
    graph = {
        "intent": "TRANSLATE",
        "entities": {
            "E1": {"type": "TextDocument", "props": {"content": body.content, "source_lang": body.source_lang or "auto"}},
        },
        "constraints": {"target_lang": body.target_lang},
    }
    oml_c = to_oml_c(graph, sft=sft)
    cid = compute_cid(oml_c)

    # Persist under tmp/oml/<cid>.cbor
    base = Path(os.environ.get("ODIN_TMP_DIR", "tmp/odin/oml"))
    base.mkdir(parents=True, exist_ok=True)
    p = base / f"{cid}.cbor"
    p.write_bytes(oml_c)

    # Sign exact bytes with OPE, binding the OML CID
    kp = _get_signing_keypair()
    ope = sign_over_content(kp, oml_c, oml_cid=cid)
    ope_min = json.dumps(ope, separators=(",", ":"))
    ope_b64 = base64.b64encode(ope_min.encode("utf-8")).decode("ascii")

    # Persist receipt next to OML (tmp/odin/receipts/<cid>.ope.json)
    receipts_dir = Path(os.environ.get("ODIN_TMP_DIR", "tmp/odin")) / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipts_dir / f"{cid}.ope.json"
    receipt_path.write_text(ope_min, encoding="utf-8")

    response.headers["X-ODIN-OML-CID"] = cid
    response.headers["X-ODIN-OML-C-Path"] = str(p)
    response.headers["X-ODIN-OPE"] = ope_b64
    response.headers["X-ODIN-OPE-KID"] = ope.get("kid", kp.kid)

    return {
        "ok": True,
        "oml_cid": cid,
        "oml_path": str(p),
        "len": len(oml_c),
        "echo": {"target_lang": body.target_lang},
        "ope": ope,
    "receipt_path": str(receipt_path),
    }


# ---- Verify endpoint ----
class VerifyIn(BaseModel):
    ope: dict
    cid: str | None = None
    path: str | None = None
    bytes_b64: str | None = None


@app.post("/v1/verify")
def verify_endpoint(body: VerifyIn):
    from libs.odin_core.odin.ope import verify_over_content
    from base64 import b64decode

    # Load bytes from file or inline; prefer inline
    content: bytes | None = None
    if body.bytes_b64:
        try:
            content = b64decode(body.bytes_b64 + "==")
        except Exception:
            raise HTTPException(status_code=400, detail="invalid bytes_b64")
    elif body.path:
        p = Path(body.path)
        if not p.exists():
            raise HTTPException(status_code=400, detail="path not found")
        content = p.read_bytes()
    else:
        raise HTTPException(status_code=400, detail="missing content (path or bytes_b64)")

    expected = body.cid
    res = verify_over_content(body.ope, content, expected_oml_cid=expected)
    return res


# ---- SFT registry endpoints ----
@app.get("/v1/sft/default")
def get_sft_default():
    sft = get_default_sft()
    # Provide both JSON-hash and CBOR-CID for compatibility
    sft_json = canonical_json_bytes(sft)
    # compute CID over canonical CBOR of SFT map
    try:
        import cbor2  # local import to avoid unused if not hit

        sft_cbor = cbor2.dumps(sft, canonical=True)
        sft_cid = compute_cid(sft_cbor)
    except Exception:
        sft_cid = None
    from libs.odin_core.odin.crypto.blake3_hash import blake3_256_b64u

    return {
        "version": 1,
        "sft": sft,
        "json_hash_b3_256_b64u": blake3_256_b64u(sft_json),
        **({"cbor_cid": sft_cid} if sft_cid else {}),
    }


# ---- Ledger stub (append-only CIDs) ----
class LedgerAppendIn(BaseModel):
    cid: str
    meta: dict | None = None


def _ledger_path() -> Path:
    root = Path(os.environ.get("ODIN_TMP_DIR", "tmp/odin"))
    led_dir = root / "ledger"
    led_dir.mkdir(parents=True, exist_ok=True)
    return led_dir / "ledger.jsonl"


@app.post("/v1/ledger/append")
def ledger_append(body: LedgerAppendIn):
    if not isinstance(body.cid, str) or not body.cid.startswith("b"):
        raise HTTPException(status_code=400, detail="invalid cid")
    entry = {"ts_ns": time.time_ns(), "cid": body.cid, "meta": body.meta or {}}
    lp = _ledger_path()
    with lp.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    # compute index by counting lines (simple for stub)
    try:
        with lp.open("r", encoding="utf-8") as f:
            idx = sum(1 for _ in f) - 1
    except Exception:
        idx = None
    return {"ok": True, "index": idx, "path": str(lp)}


@app.get("/v1/ledger")
def ledger_list(limit: int = 100):
    lp = _ledger_path()
    items = []
    if lp.exists():
        with lp.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    items.append(json.loads(line))
                except Exception:
                    continue
    return {"count": len(items[-limit:]), "items": items[-limit:]}
