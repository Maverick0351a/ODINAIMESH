# path: libs/odin_core/tests/test_ope.py
from odin.ope import OpeKeypair, sign_over_content, verify_over_content
from odin.oml import to_oml_c, compute_cid


def test_ope_sign_verify_happy_path_and_tamper_detection():
    kp = OpeKeypair.generate("k1")
    content = b"hello world"
    oml_c = to_oml_c({"msg": "hello world"})
    cid = compute_cid(oml_c)

    ope = sign_over_content(kp, content, oml_cid=cid, ts_ns=123456789)
    ok = verify_over_content(ope, content, expected_oml_cid=cid)
    assert ok["ok"] is True and ok["kid"] == "k1"

    # Tamper content
    tampered = b"hello worle"
    bad = verify_over_content(ope, tampered, expected_oml_cid=cid)
    assert bad["ok"] is False

    # Tamper OML CID
    ope2 = dict(ope)
    ope2["oml_cid"] = "b" + "a" * 52
    bad2 = verify_over_content(ope2, content, expected_oml_cid=cid)
    assert bad2["ok"] is False
