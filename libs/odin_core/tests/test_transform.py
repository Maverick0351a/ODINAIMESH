from odin.ope import OpeKeypair
from odin.transform import build_transform_subject, sign_transform_receipt


def test_transform_subject_and_receipt_roundtrip():
    input_obj = {"intent": "alpha.ask", "ask": "2+2?"}
    output_obj = {"intent": "beta.request", "task": "math.add", "args": {"a": 2, "b": 2}}
    map_obj = {"intents": {"alpha.ask": "beta.request"}}

    subj = build_transform_subject(
        input_obj=input_obj,
        output_obj=output_obj,
        sft_from="alpha@v1",
        sft_to="beta@v1",
        map_obj_or_bytes=map_obj,
        map_id="alpha@v1__beta@v1",
        out_oml_cid=None,
    )

    assert subj.v == 1 and subj.type == "transform"
    assert subj.sft_from == "alpha@v1" and subj.sft_to == "beta@v1"
    assert isinstance(subj.input_sha256_b64u, str) and isinstance(subj.output_sha256_b64u, str)
    assert isinstance(subj.map_sha256_b64u, str)

    kp = OpeKeypair.generate("k1")
    receipt = sign_transform_receipt(subject=subj, keypair=kp)

    assert receipt.v == 1
    assert "linkage_hash_b3_256_b64u" in receipt.__dict__
    env = receipt.envelope
    assert env.get("kid") == "k1"
    assert "oml_cid" in env and "ope" in env
