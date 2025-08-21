from __future__ import annotations

from typing import Any, Dict, List, Tuple

ID = "alpha@v1"


def sft_info() -> Dict[str, Any]:
    return {
        "id": ID,
        "intents": {
            "alpha.ask": {"required": ["ask", "reason"]},
            "alpha.result": {"required": ["answer", "ok"]},
        },
    }


def validate(obj: Any) -> Tuple[bool, List[str]]:
    errs: List[str] = []
    if not isinstance(obj, dict):
        return False, ["alpha: object required"]
    intent = obj.get("intent")
    if intent == "alpha.ask":
        if not isinstance(obj.get("ask"), str):
            errs.append("alpha.ask: field 'ask' (str) required")
        if not isinstance(obj.get("reason"), str):
            errs.append("alpha.ask: field 'reason' (str) required")
    elif intent == "alpha.result":
        if not isinstance(obj.get("answer"), str):
            errs.append("alpha.result: field 'answer' (str) required")
        if not isinstance(obj.get("ok"), bool):
            errs.append("alpha.result: field 'ok' (bool) required")
    else:
        errs.append(f"alpha: unknown intent '{intent}'")
    return (len(errs) == 0, errs)
