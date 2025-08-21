from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class Ledger:
    def append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Append a record and return the stored record (with ts_ns/_id as available)."""
        raise NotImplementedError

    def list(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return most recent records, newest first, up to limit."""
        raise NotImplementedError


class FileLedger(Ledger):
    """Filesystem-backed JSONL ledger under root/ledger.jsonl."""

    def __init__(self, data_dir: Path | str):
        self.root = Path(data_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        # Keep existing file name for compatibility with prior gateway index logic
        self.path = self.root / "ledger.jsonl"

    def append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        ts_ns = int(record.get("ts_ns") or time.time_ns())
        stored = {**record, "ts_ns": ts_ns}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(stored, separators=(",", ":")) + "\n")
        # Optionally compute index cheaply by counting lines; callers that need index can recompute
        try:
            with self.path.open("r", encoding="utf-8") as f:
                index = sum(1 for _ in f) - 1
        except Exception:
            index = None
        if index is not None:
            stored["_index"] = index
        stored["_path"] = str(self.path)
        return stored

    def list(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        # newest first
        out: List[Dict[str, Any]] = []
        for x in reversed(lines[-limit:]):
            x = x.strip()
            if not x:
                continue
            try:
                out.append(json.loads(x))
            except Exception:
                continue
        return out


class InMemoryLedger(Ledger):
    def __init__(self):
        self._items: List[Dict[str, Any]] = []

    def append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        ts_ns = int(record.get("ts_ns") or time.time_ns())
        stored = {**record, "ts_ns": ts_ns}
        self._items.append(stored)
        return stored

    def list(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(reversed(self._items[-limit:]))


class FirestoreLedger(Ledger):
    """
    Firestore-backed durable ledger.
    - Collection name defaults to 'odin_ledger' (override with ODIN_FIRESTORE_COLLECTION).
    - Documents keyed by ts_ns to keep natural ordering stable; collisions improbable, but
      if present we suffix "-<thread_id>".
    - Requires either ADC in cloud, or FIRESTORE_EMULATOR_HOST+GOOGLE_CLOUD_PROJECT in dev.
    """

    def __init__(self, collection: Optional[str] = None, namespace: Optional[str] = None):
        try:
            from google.cloud import firestore  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("google-cloud-firestore is not installed") from e

        self._firestore = firestore
        self.client = firestore.Client()  # ADC or emulator
        base = collection or os.getenv("ODIN_FIRESTORE_COLLECTION", "odin_ledger")
        self.collection_name = f"{base}_{namespace}" if namespace else base
        self.col_ref = self.client.collection(self.collection_name)
        self._tid = threading.get_ident()

    def append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        ts_ns = int(record.get("ts_ns") or time.time_ns())
        doc_id = str(ts_ns)
        stored = {**record, "ts_ns": ts_ns}
        try:
            self.col_ref.document(doc_id).create(stored)
        except Exception:
            doc_id = f"{ts_ns}-{self._tid}"
            stored["_id"] = doc_id
            self.col_ref.document(doc_id).set(stored)
        else:
            stored["_id"] = doc_id
        return stored

    def list(self, limit: int = 100) -> List[Dict[str, Any]]:
        q = (
            self.col_ref.order_by("ts_ns", direction=self._firestore.Query.DESCENDING).limit(limit)
        )
        return [d.to_dict() for d in q.stream()]


def create_ledger_from_env() -> Ledger:
    """
    Select ledger backend via ODIN_LEDGER_BACKEND=file|firestore|inmem
    - file: uses ODIN_DATA_DIR (default tmp/odin) under subdir 'ledger'
    - firestore: uses ADC or emulator; falls back to file on error
    - inmem: ephemeral, for tests
    """

    backend = os.getenv("ODIN_LEDGER_BACKEND", "file").lower()
    if backend in ("inmem", "memory"):
        return InMemoryLedger()
    if backend in ("firestore", "fsdb"):
        try:
            ns = os.getenv("ODIN_NAMESPACE") or None
            coll = os.getenv("ODIN_FIRESTORE_COLLECTION", "odin_ledger")
            return FirestoreLedger(collection=coll, namespace=ns)
        except Exception as e:  # pragma: no cover - optional dependency
            print(f"[ODIN] Firestore ledger unavailable ({e}); falling back to file.")
            # fall through to file
    # default to file under data dir/ledger
    root = Path(os.getenv("ODIN_DATA_DIR", "tmp/odin")) / "ledger"
    root.mkdir(parents=True, exist_ok=True)
    return FileLedger(data_dir=root)


__all__ = [
    "Ledger",
    "FileLedger",
    "InMemoryLedger",
    "FirestoreLedger",
    "create_ledger_from_env",
]
