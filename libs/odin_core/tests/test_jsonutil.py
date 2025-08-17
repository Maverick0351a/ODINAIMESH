from __future__ import annotations

from odin.jsonutil import canonical_json_bytes, try_parse_json


def test_canonical_json_bytes_sorted_and_stable():
    a = {"b": 2, "a": 1}
    b = {"a": 1, "b": 2}
    ba = canonical_json_bytes(a)
    bb = canonical_json_bytes(b)
    # sorted keys produce identical bytes; newline at end
    assert ba == bb
    assert ba.endswith(b"\n")
    assert ba == b'{"a":1,"b":2}\n'


def test_try_parse_json_ok_and_error():
    ok, err = try_parse_json('{"a":1}')
    assert err is None and ok == {"a": 1}

    bad, err2 = try_parse_json('{"a":}')
    assert bad is None and isinstance(err2, str) and err2
