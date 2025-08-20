from odin.envelope import ProofEnvelope
from odin.oml import to_oml_c
from odin.ope import OpeKeypair


def test_envelope_roundtrip():
    graph = {"intent": "ECHO", "msg": "hi"}
    oml = to_oml_c(graph)
    kp = OpeKeypair.generate("k1")
    sig = kp.private_key.sign(b"ODIN:OPE:v1|" + (0).to_bytes(8, "big") + b"|" + b"\x00"*32)
    env = ProofEnvelope.from_parts(oml, kid=kp.kid, sig_b=sig, jwks_url="http://example/jwks")
    j = env.to_json()
    assert "oml_cid" in j and "kid" in j and "ope" in j
