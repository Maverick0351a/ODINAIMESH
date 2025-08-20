from typing import Any, Dict, List, Tuple

ID = "beta@v1"


def sft_info() -> Dict[str, Any]:
    return {
        "id": ID,
        "intents": {
            "beta.request": {"required": ["prompt", "why"]},
            "beta.reply": {"required": ["output", "success"]},
        },
    }


def validate(obj: Any) -> Tuple[bool, List[str]]:
    errs: List[str] = []
    if not isinstance(obj, dict):
        return False, ["beta: object required"]
    intent = obj.get("intent")
    if intent == "beta.request":
        if not isinstance(obj.get("prompt"), str):
            errs.append("beta.request: field 'prompt' (str) required")
        if not isinstance(obj.get("why"), str):
            errs.append("beta.request: field 'why' (str) required")
    elif intent == "beta.reply":
        if not isinstance(obj.get("output"), str):
            errs.append("beta.reply: field 'output' (str) required")
        if not isinstance(obj.get("success"), bool):
            errs.append("beta.reply: field 'success' (bool) required")
    else:
        errs.append(f"beta: unknown intent '{intent}'")
    return (len(errs) == 0, errs)
