# path: libs/odin_core/odin/oml/symbols.py
"""Stable OML symbol IDs and helpers.

- Intent/Field/Rel dataclasses provide a stable constant API used by the codebase/tests.
- DEFAULT_SFT and helpers offer an alternate, compact symbol table for maps/keys.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class Intent:
    QUERY: int = 0
    PROPOSE: int = 1
    COMMIT: int = 2
    OBSERVE: int = 3
    TRANSLATE: int = 10
    SUMMARIZE: int = 11


@dataclass(frozen=True)
class Field:
    content: int = 1
    lang: int = 2
    format: int = 3
    confidence: int = 4
    mime: int = 5
    uri: int = 6
    hash: int = 7
    size: int = 8
    title: int = 9
    author: int = 10


@dataclass(frozen=True)
class Rel:
    translated_from: str = "urn:odin:rel:translated_from"
    proposes_changes_to: str = "urn:odin:rel:proposes_changes_to"
    targets: str = "urn:odin:rel:targets"
    part_of: str = "urn:odin:rel:part_of"
    references: str = "urn:odin:rel:references"
    derived_from: str = "urn:odin:rel:derived_from"


# --- Optional default symbol table (SFT) ---
# Integer keys make CBOR maps tiny & deterministic when used.
DEFAULT_SFT: Dict[str, int] = {
    "intent": 10,
    "entities": 11,
    "relations": 12,
    "constraints": 13,
    "evidence": 14,
    # intents
    "QUERY": 0,
    "PROPOSE": 1,
    "COMMIT": 2,
    "TRANSLATE": 1001,
    # common fields
    "type": 1,
    "props": 3,
    "link": 4,
    "content": 100,
    "source_lang": 101,
    "target_lang": 102,
}


def get_default_sft() -> Dict[str, int]:
    """Return a copy of the default symbol table."""
    return dict(DEFAULT_SFT)


def sym(key: str, table: Dict[str, int] | None = None) -> int | str:
    """Return integer symbol if known, else the original string (extensible)."""
    tbl = table or DEFAULT_SFT
    return tbl.get(key, key)
