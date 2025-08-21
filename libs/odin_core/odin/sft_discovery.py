from __future__ import annotations
from typing import Dict, Any, List

DISCOVERY_ID = "discovery@v1"

def validate_service_advert(obj: Dict[str, Any]) -> List[str]:
    """
    Minimal validator for discovery@v1.service.advertise
    Required:
      - intent = "service.advertise"
      - id (str, stable unique id)
      - name (str)
      - jwks_url (str) or jwks_inline (dict)
      - endpoints (dict of name->url/path)
      - intents (list[str]) - intents the service can handle
      - ttl_s (int>0) recommended; default will be applied if absent
    Optional:
      - tags (list[str])
      - metadata (dict)
    Returns: list of violation strings (empty means valid)
    """
    v: List[str] = []
    if obj.get("intent") != "service.advertise":
        v.append("intent must be 'service.advertise'")
    if not isinstance(obj.get("id"), str) or not obj.get("id", "").strip():
        v.append("field 'id' (non-empty str) required")
    if not isinstance(obj.get("name"), str) or not obj.get("name", "").strip():
        v.append("field 'name' (non-empty str) required")
    jwks_url = obj.get("jwks_url")
    jwks_inline = obj.get("jwks_inline")
    if not ((isinstance(jwks_url, str) and jwks_url.strip()) or isinstance(jwks_inline, dict)):
        v.append("one of 'jwks_url' (str) or 'jwks_inline' (dict) required")
    eps = obj.get("endpoints")
    if not isinstance(eps, dict) or not eps:
        v.append("field 'endpoints' (dict) required")
    intents = obj.get("intents")
    if not (isinstance(intents, list) and intents and all(isinstance(x, str) for x in intents)):
        v.append("field 'intents' (list[str]) required")
    ttl = obj.get("ttl_s")
    if ttl is not None and (not isinstance(ttl, int) or ttl <= 0):
        v.append("field 'ttl_s' must be int>0 when provided")
    tags = obj.get("tags")
    if tags is not None and (not isinstance(tags, list) or not all(isinstance(x, str) for x in tags)):
        v.append("field 'tags' must be list[str] when provided")
    meta = obj.get("metadata")
    if meta is not None and not isinstance(meta, dict):
        v.append("field 'metadata' must be object when provided")
    return v


def validate_service_find(obj: Dict[str, Any]) -> List[str]:
    """
    discovery@v1.service.find (not used by API directly yet, but canonical):
      - intent = "service.find"
      - intent_match?: str (intent name)
      - tag?: str
    """
    v: List[str] = []
    if obj.get("intent") != "service.find":
        v.append("intent must be 'service.find'")
    if "intent_match" in obj and not isinstance(obj.get("intent_match"), str):
        v.append("field 'intent_match' must be str when provided")
    if "tag" in obj and not isinstance(obj.get("tag"), str):
        v.append("field 'tag' must be str when provided")
    return v
