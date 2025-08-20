# Thin wrapper so you can `python -m apps.cli.odin_verify ...`
# or add a console_script later without touching core.

from libs.odin_core.odin.verify import _cli  # type: ignore

if __name__ == "__main__":
    raise SystemExit(_cli())
