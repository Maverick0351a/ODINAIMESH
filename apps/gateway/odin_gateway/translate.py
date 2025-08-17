# path: apps/gateway/odin_gateway/translate.py
from __future__ import annotations

import base64
import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from odin.oml import compute_cid, to_oml_c
from odin.ope import OpeKeypair, sign_over_content
from odin.security.keystore import load_keypair_from_env, load_keystore_from_json_env


router = APIRouter()


@lru_cache(maxsize=1)
def _get_signing_keypair() -> OpeKeypair:
    """Resolve the signing keypair from env/keystore or generate ephemeral.

    Ephemeral generation logs a warning when ODIN_DEBUG=1.
    """
    loaded = load_keypair_from_env()
    if loaded is not None:
        return loaded.keypair

    js = os.getenv("ODIN_KEYSTORE_JSON")
    if js:
        try:
            data = json.loads(js)
            active_kid = data.get("active_kid")
            keystore = load_keystore_from_json_env() or {}
            if active_kid and active_kid in keystore:
                return keystore[active_kid]
            if keystore:
                return next(iter(keystore.values()))
        except Exception:
            # fall through to ephemeral
            pass

    kp = OpeKeypair.generate("ephemeral")
    if os.getenv("ODIN_DEBUG") == "1":
        logging.warning("ODIN Gateway using ephemeral OPE keypair (no env keystore found)")
    return kp


class TranslateRequest(BaseModel):
    text: str
    source_lang: Optional[str] = None
    target_lang: Optional[str] = None


@router.post("/v1/translate")
async def translate(req: TranslateRequest, response: Response):
    if not isinstance(req.text, str) or not req.text:
        raise HTTPException(status_code=400, detail="text must be non-empty string")

    src_lang = req.source_lang or "auto"
    tgt_lang = req.target_lang or "en"

    # Build OML graph per spec
    e1 = {
        "1": "urn:schema:TextDocument",
        "3": {"content": req.text, "lang": src_lang},
    }
    e2 = {
        "1": "urn:schema:TextDocument",
        "3": {"content": req.text, "lang": tgt_lang},  # placeholder translation (echo)
    }
    relations = [["E2", "urn:oml:relation:translated_from", "E1"]]

    graph = {
        "intent": 10,
        "entities": [e1, e2],
        "relations": relations,
    }

    oml_bytes = to_oml_c(graph)
    cid = compute_cid(oml_bytes)

    out_dir = Path("tmp/oml")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{cid}.cbor"
    out_path.write_bytes(oml_bytes)

    # OPE proof over content bytes and CID
    kp = _get_signing_keypair()
    ope = sign_over_content(kp, oml_bytes, oml_cid=cid)
    ope_min = json.dumps(ope, separators=(",", ":"))
    ope_b64 = base64.b64encode(ope_min.encode("utf-8")).decode("ascii")

    response.headers["X-ODIN-OML-CID"] = cid
    response.headers["X-ODIN-OML-C-Path"] = str(out_path)
    response.headers["X-ODIN-OPE"] = ope_b64
    response.headers["X-ODIN-OPE-KID"] = ope.get("kid", kp.kid)

    return {
        "ok": True,
        "oml_cid": cid,
        "oml_bytes_len": len(oml_bytes),
        "path": str(out_path),
        "ope": ope,
    }
