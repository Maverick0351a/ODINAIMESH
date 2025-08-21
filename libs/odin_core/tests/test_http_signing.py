from odin.http_signing import body_sha256_b64u, build_http_signing_message


def test_http_signing_message_format_and_hash():
    ts_ns = 1723958400000000000  # arbitrary
    method = "post"
    path = "/v1/translate?x=1&y=2"
    body = b"{\n  \"hello\": \"world\"\n}"

    bh = body_sha256_b64u(body)
    assert isinstance(bh, str) and len(bh) > 0

    msg = build_http_signing_message(ts_ns, method, path, body)
    expect_prefix = f"v1\n{ts_ns}\nPOST\n{path}\n".encode("utf-8")
    assert msg.startswith(expect_prefix)
    assert msg.decode("utf-8").split("\n")[-1] == bh
