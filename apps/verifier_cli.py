from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from libs.odin_core.odin.verifier import verify


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="odin-verify", description="ODIN OPE verifier")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--receipt", help="Path to receipt JSON or '-' for stdin")
    src.add_argument("--headers", help="Path to JSON dict of headers")
    src.add_argument("--oml", help="Path to OML-C .cbor; requires --ope")
    p.add_argument("--ope", help="Path to OPE JSON (used with --oml)")
    p.add_argument("--cid", help="Expected OML CID; if provided, must match")
    p.add_argument("--jwks", help="JWKS (JSON, URL, or file path)")

    args = p.parse_args(argv)

    try:
        kwargs = {}
        if args.receipt:
            data = sys.stdin.read() if args.receipt == "-" else Path(args.receipt).read_text(encoding="utf-8")
            kwargs["receipt"] = json.loads(data)
        elif args.headers:
            kwargs["headers"] = json.loads(Path(args.headers).read_text(encoding="utf-8"))
        elif args.oml:
            kwargs["oml_c_path"] = args.oml
            if not args.ope:
                print("--ope is required when using --oml", file=sys.stderr)
                return 2
            kwargs["receipt"] = json.loads(Path(args.ope).read_text(encoding="utf-8"))
        if args.cid:
            kwargs["expected_cid"] = args.cid
        if args.jwks:
            kwargs["jwks"] = args.jwks

        res = verify(**kwargs)
        print(json.dumps(res.__dict__), flush=True)
        return 0 if res.ok else 1
    except json.JSONDecodeError:
        print("invalid JSON input", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
