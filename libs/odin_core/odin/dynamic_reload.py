from __future__ import annotations

import os
import time
import json
import hashlib
import logging
import secrets
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

try:  # optional; used when files are YAML
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore

log = logging.getLogger("odin.dynamic")


# ---------- Storage Abstraction ----------


class Storage:
    def get_bytes(self, uri: str) -> bytes:
        raise NotImplementedError

    def get_text(self, uri: str) -> str:
        return self.get_bytes(uri).decode("utf-8")

    def etag(self, uri: str) -> str:
        raise NotImplementedError


class LocalStorage(Storage):
    def _path(self, uri: str) -> str:
        return uri[7:] if uri.startswith("file://") else uri

    def get_bytes(self, uri: str) -> bytes:
        p = self._path(uri)
        with open(p, "rb") as f:
            return f.read()

    def etag(self, uri: str) -> str:
        b = self.get_bytes(uri)
        return hashlib.sha256(b).hexdigest()


class GCSStorage(Storage):
    def __init__(self):
        try:
            from google.cloud import storage  # type: ignore
        except Exception as e:  # pragma: no cover - optional dependency
            raise RuntimeError("google-cloud-storage is required for GCS backend") from e
        self._client = storage.Client()

    @staticmethod
    def _parse(uri: str):
        if not uri.startswith("gs://"):
            raise ValueError(f"Invalid GCS URI: {uri}")
        parsed = urlparse(uri)
        bucket = parsed.netloc
        # parsed.path keeps leading '/'; strip it
        blob_name = parsed.path.lstrip("/")
        return bucket, blob_name

    def get_bytes(self, uri: str) -> bytes:
        from google.cloud import exceptions  # type: ignore

        bucket, blob_name = self._parse(uri)
        bucket_ref = self._client.bucket(bucket)
        blob = bucket_ref.blob(blob_name)
        try:
            return blob.download_as_bytes()
        except exceptions.NotFound as e:
            raise FileNotFoundError(f"GCS object not found: {uri}") from e

    def etag(self, uri: str) -> str:
        bucket, blob_name = self._parse(uri)
        bucket_ref = self._client.bucket(bucket)
        blob = bucket_ref.blob(blob_name)
        blob.reload()  # populates etag & generation
        # Include generation to avoid weak validators across overwrites
        return f"{blob.etag}:{blob.generation}"


# ---------- Parsers ----------


def parse_yaml_or_json(text: str) -> Any:
    s = text.strip()
    if s.startswith("{") or s.startswith("["):
        return json.loads(text)
    if yaml is None:
        raise ValueError("YAML parser not available; install pyyaml or use JSON")
    return yaml.safe_load(text)  # type: ignore[misc]


# ---------- Dynamic Assets ----------


@dataclass
class DynamicAsset:
    name: str
    uri: str
    storage: Storage
    ttl_secs: int
    parser: Callable[[str], Any] = parse_yaml_or_json

    etag: str = ""
    loaded_at: float = 0.0
    checked_at: float = 0.0
    value: Any = None
    last_error: Optional[str] = None

    def maybe_reload(self, force: bool = False) -> None:
        now = time.time()
        due = (now - self.loaded_at) >= self.ttl_secs
        should_check = force or due or (now - self.checked_at) >= 1.0  # coalesce checks
        if not should_check:
            return
        try:
            new_etag = self.storage.etag(self.uri)
            self.checked_at = now
            if force or new_etag != self.etag:
                text = self.storage.get_text(self.uri)
                self.value = self.parser(text)
                self.etag = new_etag
                self.loaded_at = now
                self.last_error = None
                log.info("Reloaded %s from %s (etag=%s)", self.name, self.uri, self.etag)
        except Exception as e:  # pragma: no cover - robustness
            self.last_error = f"{type(e).__name__}: {e}"
            # Keep serving the last good value; just log the failure
            log.warning("Failed reloading %s (%s): %s", self.name, self.uri, type(e).__name__, exc_info=e)


@dataclass
class DynamicReloader:
    storage: Storage
    policy_uri: str
    sft_registry_uri: str
    sft_map_dir: str
    ttl_secs: int = 30

    policy: DynamicAsset = field(init=False)
    sft_registry: DynamicAsset = field(init=False)
    map_cache: Dict[str, DynamicAsset] = field(default_factory=dict, init=False)

    def __post_init__(self):
        self.policy = DynamicAsset("HEL policy", self.policy_uri, self.storage, self.ttl_secs)
        self.sft_registry = DynamicAsset("SFT registry", self.sft_registry_uri, self.storage, self.ttl_secs)
        # Prime on startup
        self.policy.maybe_reload(force=True)
        self.sft_registry.maybe_reload(force=True)

    # --- Public getters used by request handlers ---

    def get_policy(self) -> Any:
        self.policy.maybe_reload()
        return self.policy.value

    def get_sft_registry(self) -> Any:
        self.sft_registry.maybe_reload()
        return self.sft_registry.value

    def get_map(self, map_name: str) -> Any:
        asset = self.map_cache.get(map_name)
        if not asset:
            # Try .json, .yaml, .yml (in that order)
            base = self.sft_map_dir.rstrip("/")
            candidates = [
                f"{base}/{map_name}.json",
                f"{base}/{map_name}.yaml",
                f"{base}/{map_name}.yml",
            ]
            # Resolve first that exists (Local can check directly; GCS loads best-effort)
            chosen = None
            for uri in candidates:
                try:
                    _ = self.storage.etag(uri)
                    chosen = uri
                    break
                except Exception:
                    continue
            if not chosen:
                # Fall back to .json path (will raise on access) to surface a clear error
                chosen = candidates[0]
            asset = DynamicAsset(f"SFT map:{map_name}", chosen, self.storage, self.ttl_secs)
            # Load immediately so errors show up deterministically
            asset.maybe_reload(force=True)
            self.map_cache[map_name] = asset
        else:
            asset.maybe_reload()
        return asset.value

    # --- Admin helpers ---

    def force_reload(self, target: str = "all") -> Dict[str, Any]:
        target = target.lower()
        if target in ("all", "policy"):
            self.policy.maybe_reload(force=True)
        if target in ("all", "sft", "registry"):
            self.sft_registry.maybe_reload(force=True)
        if target.startswith("map:"):
            name = target.split(":", 1)[1]
            # Drop cache and reload
            if name in self.map_cache:
                del self.map_cache[name]
            self.get_map(name)
        return self.status()

    def status(self) -> Dict[str, Any]:
        return {
            "policy_dynamic": True,
            "sft_dynamic": True,
            "policy": {
                "uri": self.policy.uri,
                "etag": self.policy.etag,
                "loaded_at": self.policy.loaded_at,
                "last_error": self.policy.last_error,
            },
            "sft_registry": {
                "uri": self.sft_registry.uri,
                "etag": self.sft_registry.etag,
                "loaded_at": self.sft_registry.loaded_at,
                "last_error": self.sft_registry.last_error,
            },
            "maps_cached": [
                {"name": k, "uri": v.uri, "etag": v.etag, "loaded_at": v.loaded_at, "last_error": v.last_error}
                for k, v in self.map_cache.items()
            ],
            "ttl_secs": self.ttl_secs,
        }


# ---------- Admin guard (shared) ----------


def require_admin(request_headers: Dict[str, str]) -> None:
    expected = os.getenv("ODIN_ADMIN_KEY", "")
    provided = request_headers.get("x-odin-admin-key") or request_headers.get("X-ODIN-Admin-Key")
    if not expected or not provided or not secrets.compare_digest(expected, provided):
        raise PermissionError("forbidden: admin key missing or invalid")


# ---------- Factory ----------


def make_storage() -> Storage:
    backend = (os.getenv("ODIN_STORAGE") or "gcs").lower()
    if backend in ("local", "file"):
        return LocalStorage()
    if backend == "gcs":
        return GCSStorage()
    raise ValueError(f"Unknown ODIN_STORAGE backend: {backend}")


def make_reloader() -> DynamicReloader:
    storage = make_storage()
    return DynamicReloader(
        storage=storage,
        policy_uri=os.getenv("ODIN_POLICY_URI", "gs://odin-mesh-data/policy/hel.yaml"),
        sft_registry_uri=os.getenv("ODIN_SFT_REGISTRY_URI", "gs://odin-mesh-data/sft/registry.json"),
        sft_map_dir=os.getenv("ODIN_SFT_MAP_DIR", "gs://odin-mesh-data/sft/maps"),
        ttl_secs=int(os.getenv("ODIN_DYNAMIC_TTL", "30")),
    )


__all__ = [
    "Storage",
    "LocalStorage",
    "GCSStorage",
    "DynamicAsset",
    "DynamicReloader",
    "parse_yaml_or_json",
    "require_admin",
    "make_storage",
    "make_reloader",
]
