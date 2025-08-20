from libs.odin_core.odin.redaction import apply_redactions


def test_redacts_top_level_field():
    obj = {"password": "secret", "ok": True}
    out = apply_redactions(obj, ["password"]) 
    assert out["password"] == "***"
    assert out["ok"] is True


def test_redacts_nested_and_wildcard_in_list():
    obj = {
        "user": {"email": "test@example.com", "names": [
            {"secret": 1}, {"secret": 2}, {"other": 3}
        ]}
    }
    out = apply_redactions(obj, ["user.email", "user.names.*.secret"]) 
    assert out["user"]["email"] == "***"
    # Both secrets masked, unrelated item preserved
    masked = [x.get("secret") for x in out["user"]["names"]]
    assert masked[:2] == ["***", "***"]
    assert out["user"]["names"][2]["other"] == 3
