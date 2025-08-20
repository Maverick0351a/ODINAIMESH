from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from typing import Optional, Iterable, Dict, Any
from datetime import datetime, timezone


HDR_OML_C_URL = "X-ODIN-OML-C-URL"
HDR_RECEIPT_URL = "X-ODIN-Receipt-URL"


_GLOBAL_INMEM: "InMemoryStorage | None" = None
_TRANSFORM_RCPT_CACHE: dict[str, bytes] = {}


class Storage:
    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        raise NotImplementedError

    def get_bytes(self, key: str) -> bytes:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def list(self, prefix: str) -> Iterable[str]:
        raise NotImplementedError

    # Optional: return a public URL if available (e.g., CDN); default None
    def public_url(self, key: str) -> Optional[str]:
        return None

    # Optional: return a time-bound signed URL; default None
    def signed_url(self, key: str, ttl_s: int = 600) -> Optional[str]:
        return None

    # Prefer a public URL; if enabled, fall back to a signed URL
    def url_for(self, key: str) -> Optional[str]:
        url = self.public_url(key)
        if url:
            return url
        if os.getenv("ODIN_GCS_SIGN_URLS", "0") in ("1", "true", "yes"):
            try:
                ttl = int(os.getenv("ODIN_GCS_SIGN_TTL", "600"))
            except Exception:
                ttl = 600
            try:
                return self.signed_url(key, ttl)
            except Exception:
                return None
        return None


def cache_transform_receipt_set(out_cid: str, data: bytes) -> None:
    """Store a transform receipt in an in-process cache keyed by out_cid."""
    try:
        _TRANSFORM_RCPT_CACHE[out_cid] = data
    except Exception:
        pass


def cache_transform_receipt_get(out_cid: str) -> Optional[bytes]:
    """Retrieve a cached transform receipt by out_cid if present."""
    try:
        return _TRANSFORM_RCPT_CACHE.get(out_cid)
    except Exception:
        return None


def receipt_metadata_from_env() -> Optional[Dict[str, str]]:
    """Optional metadata for receipts persistence.

    If ODIN_RECEIPT_TTL_DAYS is set to a positive integer, returns a metadata
    dict including an absolute expiration timestamp in UTC and the ttl days.
    The exact handling of this metadata depends on the backend (e.g. GCS
    lifecycle rules can match custom metadata; Firestore writers can map it
    to an expires_at field).
    """
    try:
        ttl_days = int(os.getenv("ODIN_RECEIPT_TTL_DAYS", "0") or 0)
    except Exception:
        ttl_days = 0
    if ttl_days <= 0:
        return None
    try:
        expires = datetime.now(timezone.utc) + timedelta(days=ttl_days)
        # RFC3339 format with Z
        iso = expires.isoformat().replace("+00:00", "Z")
        return {"odin_expires_at": iso, "odin_ttl_days": str(ttl_days)}
    except Exception:
        return None


class FileStorage(Storage):
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = self.root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None, metadata: Optional[Dict[str, str]] = None) -> str:
        path = self._path(key)
        path.write_bytes(data)
        return str(path)

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def list(self, prefix: str) -> Iterable[str]:
        base = self.root / prefix
        if not base.exists():
            return []
        for p in base.rglob("*"):
            if p.is_file():
                yield str(p.relative_to(self.root)).replace("\\", "/")


class InMemoryStorage(Storage):
    """Lightweight in-memory storage (useful in tests)."""

    def __init__(self) -> None:
        self._mem: Dict[str, bytes] = {}

    def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None, metadata: Optional[Dict[str, str]] = None) -> str:
        self._mem[key] = data
        return f"inmem://{key}"

    def get_bytes(self, key: str) -> bytes:
        return self._mem[key]

    def exists(self, key: str) -> bool:
        return key in self._mem

    def list(self, prefix: str) -> Iterable[str]:
        return [k for k in self._mem if k.startswith(prefix)]


class GcsStorage(Storage):
    def __init__(self, bucket: str, prefix: str = ""):
        try:
            from google.cloud import storage as gcs  # type: ignore
        except Exception as e:  # pragma: no cover - optional dependency
            raise RuntimeError("google-cloud-storage not installed") from e
        self._client = gcs.Client()
        # Validate bucket exists to fail fast with a helpful error
        existing = getattr(self._client, "lookup_bucket", None)
        if callable(existing):  # modern clients have lookup_bucket
            b = existing(bucket)
            if b is None:
                raise RuntimeError(f"GCS bucket '{bucket}' not found or not accessible")
            self._bucket = b
        else:
            # Fallback: construct and probe
            b = self._client.bucket(bucket)
            try:
                if not b.exists():  # type: ignore[attr-defined]
                    raise RuntimeError(f"GCS bucket '{bucket}' not found or not accessible")
            except Exception:
                # If exists() API isn't available, leave as-is and let operations raise
                pass
            self._bucket = b
        self._prefix = prefix.strip("/")
        # Optional public host (e.g., CDN) and signed-URL toggle
        self._public_host = os.getenv("ODIN_GCS_PUBLIC_HOST")
        self._signing_enabled = os.getenv("ODIN_GCS_SIGN_URLS", "0") in ("1", "true", "yes")

    def _name(self, key: str) -> str:
        return f"{self._prefix}/{key}" if self._prefix else key

    def _blob(self, key: str):
        return self._bucket.blob(self._name(key))

    def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None, metadata: Optional[Dict[str, str]] = None) -> str:
        b = self._blob(key)
        if metadata:
            b.metadata = metadata
        # Important: pass content_type to upload_from_string so the upload
        # header matches the metadata; otherwise GCS rejects with 400.
        if content_type:
            b.upload_from_string(data, content_type=content_type)
        else:
            b.upload_from_string(data)
        return f"gs://{self._bucket.name}/{b.name}"

    def get_bytes(self, key: str) -> bytes:
        return self._blob(key).download_as_bytes()

    def exists(self, key: str) -> bool:
        return self._blob(key).exists()

    def list(self, prefix: str) -> Iterable[str]:
        prefix_full = self._name(prefix)
        for b in self._bucket.list_blobs(prefix=prefix_full):
            if self._prefix:
                name = b.name[len(self._prefix) + 1 :]
            else:
                name = b.name
            yield name

    def public_url(self, key: str) -> Optional[str]:
        if not self._public_host:
            return None
        # Include bucket segment since public host may front multiple buckets
        path = self._name(key)
        return f"{self._public_host.rstrip('/')}/{self._bucket.name}/{path}"

    def signed_url(self, key: str, ttl_s: int = 600) -> Optional[str]:
        if not self._signing_enabled:
            return None
        blob = self._blob(key)
        # Requires service account with sign permission
        return blob.generate_signed_url(version="v4", expiration=timedelta(seconds=ttl_s))


# Canonical object keys

def key_oml(cid: str) -> str:
    return f"oml/{cid}.cbor"


def key_receipt(cid: str) -> str:
    return f"receipts/{cid}.ope.json"


def key_map(name: str) -> str:
    return f"sft_maps/{name}"


def key_transform_receipt(out_cid: str) -> str:
    """Storage key for transform receipts, keyed by output content hash (base64url).

    We intentionally use a different namespace from OPE receipts. The file format is JSON.
    """
    return f"receipts/transform/{out_cid}.json"


def create_storage_from_env() -> Storage:
    backend = os.getenv("ODIN_STORAGE_BACKEND", "local").lower()
    if backend == "gcs":
        bucket = os.environ["ODIN_GCS_BUCKET"]
        prefix = os.getenv("ODIN_GCS_PREFIX", "odin")
        try:
            return GcsStorage(bucket=bucket, prefix=prefix)
        except Exception as e:
            # Optional fallback if configured
            fb = os.getenv("ODIN_STORAGE_FALLBACK", "").lower()
            if fb in {"local", "file"}:
                root = Path(os.getenv("ODIN_DATA_DIR", "tmp/odin"))
                # Emit a small hint for operators without introducing logging deps
                print(f"[odin] GCS storage unavailable ({e}); falling back to FileStorage at {root}")
                return FileStorage(root)
            if fb in {"inmem", "memory", "mem"}:
                print(f"[odin] GCS storage unavailable ({e}); falling back to InMemoryStorage")
                return InMemoryStorage()
            raise
    if backend == "inmem":
        global _GLOBAL_INMEM
        if _GLOBAL_INMEM is None:
            _GLOBAL_INMEM = InMemoryStorage()
        return _GLOBAL_INMEM
    # default local
    root = Path(os.getenv("ODIN_DATA_DIR", "tmp/odin"))
    return FileStorage(root)


__all__ = [
    "Storage",
    "FileStorage",
    "InMemoryStorage",
    "GcsStorage",
    "HDR_OML_C_URL",
    "HDR_RECEIPT_URL",
    "key_oml",
    "key_receipt",
    "key_transform_receipt",
    "key_map",
    "create_storage_from_env",
    "cache_transform_receipt_set",
    "cache_transform_receipt_get",
    "receipt_metadata_from_env",
]
