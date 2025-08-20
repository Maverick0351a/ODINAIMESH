from libs.odin_core.odin.translate import (
    SftMap,
    TranslateError,
    clear_sft_registry,
    register_sft,
    translate,
)

def test_identity_ok():
    clear_sft_registry()
    register_sft("test/A@1", lambda obj: [])  # permissive
    m = SftMap(from_sft="test/A@1", to_sft="test/A@1")
    inp = {"intent": "greet", "user_name": "Maver"}
    out = translate(inp, m)
    assert out == inp

def test_field_rename_const_drop_intent():
    clear_sft_registry()

    def va(obj):
        # Input requires user_name
        return [] if "user_name" in obj else ["missing:user_name"]

    def vb(obj):
        # Output requires name and no debug
        errs = []
        if "name" not in obj:
            errs.append("missing:name")
        if "debug" in obj:
            errs.append("forbid:debug")
        return errs

    register_sft("test/A@1", va)
    register_sft("test/B@1", vb)

    m = SftMap(
        from_sft="test/A@1",
        to_sft="test/B@1",
        intents={"greet": "say_hello"},
        fields={"user_name": "name"},
        const={"version": "1"},
        drop=["debug"],
    )

    inp = {"intent": "greet", "user_name": "Maver", "debug": True}
    out = translate(inp, m)
    assert out["intent"] == "say_hello"
    assert out["name"] == "Maver"
    assert out["version"] == "1"
    assert "debug" not in out

def test_invalid_input_raises():
    clear_sft_registry()
    register_sft("test/A@1", lambda obj: ["missing:user_name"])
    register_sft("test/B@1", lambda obj: [])
    m = SftMap(from_sft="test/A@1", to_sft="test/B@1")
    try:
        translate({"intent": "X"}, m)
        assert False, "expected TranslateError"
    except TranslateError as te:
        assert te.code == "odin.translate.input_invalid"
        assert te.violations

def test_invalid_output_raises():
    clear_sft_registry()
    register_sft("test/A@1", lambda obj: [])
    # Require 'name' but map won't provide it -> invalid
    register_sft("test/B@1", lambda obj: [] if "name" in obj else ["missing:name"])
    m = SftMap(from_sft="test/A@1", to_sft="test/B@1")  # identity -> won't create 'name'
    try:
        translate({"intent": "ok"}, m)
        assert False, "expected TranslateError"
    except TranslateError as te:
        assert te.code == "odin.translate.output_invalid"
        assert te.violations
