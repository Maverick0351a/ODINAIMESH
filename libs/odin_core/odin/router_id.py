import os, socket, secrets


def get_router_id() -> str:
    rid = os.getenv("ODIN_ROUTER_ID")
    if rid:
        return rid.strip()
    # stable-ish default
    return socket.gethostname().lower()


def new_trace_id() -> str:
    # 32 hex chars, collision-safe for our purposes
    return secrets.token_hex(16)


def append_forwarded_by(existing: str | None, router_id: str) -> str:
    if not existing:
        return router_id
    parts = [p.strip() for p in existing.split(",") if p.strip()]
    parts.append(router_id)
    return ",".join(parts)


def hop_number(forwarded_by: str) -> int:
    if not forwarded_by:
        return 0
    return len([p for p in forwarded_by.split(",") if p.strip()])
