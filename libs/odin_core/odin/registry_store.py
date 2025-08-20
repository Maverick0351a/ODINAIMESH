from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .registry import RegistryError


class RegistryStore:
    def upsert(self, service_id: str, doc: Dict[str, Any]) -> None:
        raise NotImplementedError

    def get(self, service_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def list(
        self,
        service: Optional[str] = None,
        sft: Optional[str] = None,
        active_only: bool = True,
        now_ns: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def delete(self, service_id: str) -> bool:
        raise NotImplementedError


class InMemoryRegistry(RegistryStore):
    def __init__(self):
        self._db: Dict[str, Dict[str, Any]] = {}

    def upsert(self, service_id: str, doc: Dict[str, Any]) -> None:
        self._db[service_id] = dict(doc)

    def get(self, service_id: str) -> Optional[Dict[str, Any]]:
        doc = self._db.get(service_id)
        return dict(doc) if doc else None

    def list(
        self,
        service: Optional[str] = None,
        sft: Optional[str] = None,
        active_only: bool = True,
        now_ns: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        items = list(self._db.values())
        if active_only:
            n = now_ns or 0
            items = [d for d in items if d.get("expires_ts_ns", 0) == 0 or d.get("expires_ts_ns", 0) > n]
        if service:
            items = [d for d in items if d.get("service") == service]
        if sft:
            items = [d for d in items if sft in (d.get("sft") or [])]
        return items[:limit]

    def delete(self, service_id: str) -> bool:
        return self._db.pop(service_id, None) is not None


class FirestoreRegistry(RegistryStore):
    def __init__(self, collection: str, namespace: Optional[str] = None):
        try:
            from google.cloud import firestore  # type: ignore
        except Exception as e:
            raise RegistryError(f"google-cloud-firestore not available: {e}")

        self._client = firestore.Client()
        suffix = f"_{namespace}" if namespace else ""
        self._col = self._client.collection(f"{collection}{suffix}")

    def upsert(self, service_id: str, doc: Dict[str, Any]) -> None:
        self._col.document(service_id).set(doc)

    def get(self, service_id: str) -> Optional[Dict[str, Any]]:
        snap = self._col.document(service_id).get()
        if not snap.exists:
            return None
        d = snap.to_dict() or {}
        d["id"] = service_id
        return d

    def list(
        self,
        service: Optional[str] = None,
        sft: Optional[str] = None,
        active_only: bool = True,
        now_ns: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        # Start with base query
        q = self._col.limit(limit)

        # Simple server-side filters when possible
        if service:
            q = q.where("service", "==", service)
        if active_only and now_ns:
            q = q.where("expires_ts_ns", ">", now_ns)

        docs = [d.to_dict() | {"id": d.id} for d in q.stream()]

        # Client-side filter for SFT (array-contains would be better, but avoid requiring index)
        if sft:
            docs = [d for d in docs if sft in (d.get("sft") or [])]

        return docs

    def delete(self, service_id: str) -> bool:
        ref = self._col.document(service_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True


def create_registry_from_env() -> RegistryStore:
    backend = (os.getenv("ODIN_REGISTRY_BACKEND") or "inmem").lower()
    if backend == "firestore":
        collection = os.getenv("ODIN_FIRESTORE_COLLECTION") or "odin_registry"
        ns = os.getenv("ODIN_NAMESPACE") or None
        return FirestoreRegistry(collection=collection, namespace=ns)
    return InMemoryRegistry()
