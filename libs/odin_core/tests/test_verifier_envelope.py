import json
from odin.verifier import verify


def test_verify_from_envelope_headers_inline(monkeypatch):
    # Minimal synthetic envelope that mirrors gateway output shape
    oml_c_b64 = "AA"  # decodes to b"\x00"
    env = {
        "oml_cid": "b" + "a" * 20,  # not enforced when we pass different bytes; expected_cid is optional
        "kid": "k1",
        "ope": json.dumps({"v":1,"alg":"Ed25519","ts_ns":0,"kid":"k1","pub_b64u":"","content_hash_b3_256_b64u":"","sig_b64u":""}).encode("utf-8").hex(),
    }
    # Should fail due to invalid base64url ope
    res = verify(envelope=env)
    assert not res.ok and res.reason in ("invalid_envelope_ope", "missing_oml_c")
