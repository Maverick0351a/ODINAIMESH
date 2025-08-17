from libs.odin_core.odin.oml import to_oml_c, from_oml_c, compute_cid, get_default_sft


def test_roundtrip_and_cid_stability():
    sft = get_default_sft()
    g1 = {"intent": "COMMIT", "entities": {"E1": {"type": "Doc", "props": {"content": "hi"}}}}
    g2 = {"entities": {"E1": {"props": {"content": "hi"}, "type": "Doc"}}, "intent": "COMMIT"}  # permuted keys

    b1 = to_oml_c(g1, sft=sft)
    b2 = to_oml_c(g2, sft=sft)
    assert b1 == b2, "canonical OML-C must match"

    cid1 = compute_cid(b1)
    cid2 = compute_cid(b2)
    assert cid1 == cid2 and cid1.startswith("b")

    obj = from_oml_c(b1)
    assert isinstance(obj, dict)
