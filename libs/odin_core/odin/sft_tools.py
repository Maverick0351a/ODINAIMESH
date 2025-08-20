"""
Minimal SFT validators for:
- odin.task@v1: odin.task.request / odin.task.reply
- openai.tool@v1: openai.tool.call / openai.tool.result

Validators return (ok, violations) where violations is a list of dicts
with keys {code, path, message} for richer error reporting.
"""
from __future__ import annotations

from typing import Tuple, List, Dict, Any

# Public IDs
ODIN_TASK_ID = "odin.task@v1"
OPENAI_TOOL_ID = "openai.tool@v1"


def sft_info_odin_task() -> Dict[str, Any]:
    return {
        "id": ODIN_TASK_ID,
        "intents": {
            "odin.task.request": {"required": ["task", "args"]},
            "odin.task.reply": {"required": ["ok"]},  # result required when ok=true
        },
    }


def sft_info_openai_tool() -> Dict[str, Any]:
    return {
        "id": OPENAI_TOOL_ID,
        "intents": {
            "openai.tool.call": {"required": ["tool_name", "arguments"]},
            "openai.tool.result": {"required": ["ok"]},
        },
    }


def validate_odin_task(obj: Dict[str, Any]) -> Tuple[bool, List[Dict[str, str]]]:
    v: List[Dict[str, str]] = []
    intent = obj.get("intent")
    if intent not in ("odin.task.request", "odin.task.reply"):
        v.append({"code": "intent.invalid", "path": "//intent", "message": "unknown intent"})
    if intent == "odin.task.request":
        if "task" not in obj:
            v.append({"code": "field.missing", "path": "/task", "message": "task required"})
        if "args" not in obj:
            v.append({"code": "field.missing", "path": "/args", "message": "args required"})
        # 'reason' optional but recommended
    if intent == "odin.task.reply":
        if "ok" not in obj:
            v.append({"code": "field.missing", "path": "/ok", "message": "ok required"})
        if obj.get("ok") and "result" not in obj:
            v.append({"code": "field.missing", "path": "/result", "message": "result required when ok=true"})
    return (len(v) == 0, v)


def validate_openai_tool(obj: Dict[str, Any]) -> Tuple[bool, List[Dict[str, str]]]:
    v: List[Dict[str, str]] = []
    intent = obj.get("intent")
    if intent not in ("openai.tool.call", "openai.tool.result"):
        v.append({"code": "intent.invalid", "path": "//intent", "message": "unknown intent"})
    if intent == "openai.tool.call":
        if "tool_name" not in obj:
            v.append({"code": "field.missing", "path": "/tool_name", "message": "tool_name required"})
        if "arguments" not in obj:
            v.append({"code": "field.missing", "path": "/arguments", "message": "arguments required"})
        # 'reason' optional
    if intent == "openai.tool.result":
        if "ok" not in obj:
            v.append({"code": "field.missing", "path": "/ok", "message": "ok required"})
        # 'content' optional when ok=false
    return (len(v) == 0, v)


# Best-effort registration into the translate registry at import time.
try:  # pragma: no cover
    from .translate import register_sft

    register_sft(ODIN_TASK_ID, validate_odin_task)
    register_sft(OPENAI_TOOL_ID, validate_openai_tool)
except Exception:
    # If translate is unavailable during import, registry seeding in translate.clear_sft_registry
    # will attempt to add these validators as well.
    pass
