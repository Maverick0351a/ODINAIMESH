from __future__ import annotations

import base64
import json
from pathlib import Path

from libs.odin_core.odin.oml import to_oml_c, compute_cid
from libs.odin_core.odin.ope import OpeKeypair, sign_over_content
from libs.odin_core.odin.verifier import verify


def test_verify_from_receipt(tmp_path):
    # Build OML and sign
    oml = to_oml_c({"a": 1})
    cid = compute_cid(oml)
    kp = OpeKeypair.generate("kid1")
    ope = sign_over_content(kp, oml, oml_cid=cid)
    rec = {"oml_cid": cid, "ope": ope, "oml_c_b64": base64.b64encode(oml).decode("ascii")}

    res = verify(receipt=rec)
    assert res.ok and res.cid == cid and res.kid == "kid1"


def test_verify_from_headers(tmp_path, monkeypatch):
    oml = to_oml_c({"b": 2})
    cid = compute_cid(oml)
    kp = OpeKeypair.generate("kid2")
    ope = sign_over_content(kp, oml, oml_cid=cid)
    # Emulate gateway headers
    headers = {
        "X-ODIN-OML-CID": cid,
        "X-ODIN-OPE": base64.urlsafe_b64encode(json.dumps(ope).encode("utf-8")).decode("ascii").rstrip("="),
    }

    p = tmp_path / f"{cid}.cbor"
    p.write_bytes(oml)
    headers["X-ODIN-OML-C-Path"] = str(p)

    res = verify(headers=headers)
    assert res.ok and res.cid == cid and res.kid == "kid2"


def test_verify_cid_mismatch(tmp_path):
    oml = to_oml_c({"x": 1})
    cid = compute_cid(oml)
    kp = OpeKeypair.generate("kid3")
    ope = sign_over_content(kp, oml, oml_cid=cid)
    rec = {"oml_cid": "bnotthesame", "ope": ope, "oml_c_b64": base64.b64encode(oml).decode("ascii")}
    res = verify(receipt=rec)
    assert not res.ok and res.reason == "cid_mismatch"
