from __future__ import annotations

import base64
import json
from pathlib import Path

from libs.odin_core.odin.oml import to_oml_c, compute_cid
from libs.odin_core.odin.ope import OpeKeypair, sign_over_content
from libs.odin_core.odin.verify import _cli


def test_cli_receipt_ok(tmp_path, capsys):
    oml = to_oml_c({"m": 1})
    cid = compute_cid(oml)
    kp = OpeKeypair.generate("kidc1")
    ope = sign_over_content(kp, oml, oml_cid=cid)
    rec = {"oml_cid": cid, "ope": ope, "oml_c_b64": base64.b64encode(oml).decode("ascii")}
    p = tmp_path / "rec.json"
    p.write_text(json.dumps(rec), encoding="utf-8")

    code = _cli(["--receipt", str(p)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"] is True and out["cid"] == cid


def test_cli_usage_error(tmp_path, capsys):
    # Missing --ope when using --oml
    omlp = tmp_path / "f.cbor"
    omlp.write_bytes(b"deadbeef")
    code = _cli(["--oml", str(omlp)])
    assert code == 2
