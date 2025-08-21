# path: libs/odin_core/odin/security/keystore.py
"""Key management utilities for ODIN.

- load_keypair_from_env(): ODIN_SIGNING_KID, ODIN_SIGNING_PRIVATE_KEY_B64, ODIN_SIGNING_PUBLIC_KEY_B64
- load_keystore_from_json_env(): ODIN_KEYSTORE_JSON with
  {"active_kid":"k1","keys":[{"kid":"k1","priv_b64":"...","pub_b64":"...","active":true}]}
"""
from __future__ import annotations

import json
import os
from base64 import urlsafe_b64decode
from dataclasses import dataclass
from typing import Dict, Optional
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization

from ..ope import OpeKeypair


@dataclass
class LoadedKeypair:
    kid: str
    keypair: OpeKeypair


def _load_keypair_from_raw(kid: str, priv_b64: str, pub_b64: str) -> OpeKeypair:
    priv_raw = urlsafe_b64decode(priv_b64 + "==")
    pub_raw = urlsafe_b64decode(pub_b64 + "==")
    priv = Ed25519PrivateKey.from_private_bytes(priv_raw)
    pub = Ed25519PublicKey.from_public_bytes(pub_raw)
    # Normalize via serialization to ensure consistent materials
    priv_ser = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_ser = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    priv2 = Ed25519PrivateKey.from_private_bytes(priv_ser)
    pub2 = Ed25519PublicKey.from_public_bytes(pub_ser)
    return OpeKeypair(kid=kid, private_key=priv2, public_key=pub2)


def load_keypair_from_env() -> Optional[LoadedKeypair]:
    kid = os.getenv("ODIN_SIGNING_KID")
    priv_b64 = os.getenv("ODIN_SIGNING_PRIVATE_KEY_B64")
    pub_b64 = os.getenv("ODIN_SIGNING_PUBLIC_KEY_B64")
    if not (kid and priv_b64 and pub_b64):
        return None
    kp = _load_keypair_from_raw(kid, priv_b64, pub_b64)
    return LoadedKeypair(kid=kid, keypair=kp)


def load_keystore_from_json_env() -> Optional[Dict[str, OpeKeypair]]:
    js = os.getenv("ODIN_KEYSTORE_JSON")
    if not js:
        return None
    data = json.loads(js)
    keys_list = data.get("keys", [])
    keystore: Dict[str, OpeKeypair] = {}
    for entry in keys_list:
        kid = entry.get("kid")
        priv_b64 = entry.get("priv_b64")
        pub_b64 = entry.get("pub_b64")
        if not (kid and priv_b64 and pub_b64):
            continue
        keystore[kid] = _load_keypair_from_raw(kid, priv_b64, pub_b64)
    # Indicate active_kid with presence; callers can read data["active_kid"]
    return keystore


# --- File-based keystore (persist across restarts) ---
def _b64u(raw: bytes) -> str:
    from base64 import urlsafe_b64encode

    return urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def export_keystore(keystore: Dict[str, OpeKeypair], active_kid: Optional[str]) -> Dict[str, object]:
    """Export keystore to JSON-serializable dict (no private leakage beyond raw key material)."""
    keys = []
    for kid, kp in keystore.items():
        priv_raw = kp.private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_raw = kp.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        keys.append({"kid": kid, "priv_b64": _b64u(priv_raw), "pub_b64": _b64u(pub_raw), "active": kid == active_kid})
    return {"active_kid": active_kid, "keys": keys}


def load_keystore_from_file(path: str) -> tuple[Dict[str, OpeKeypair], Optional[str]]:
    """Load keystore JSON from file; returns (mapping, active_kid)."""
    p = os.fspath(path)
    if not os.path.exists(p):
        return {}, None
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    mapping: Dict[str, OpeKeypair] = {}
    for ent in data.get("keys", []):
        kid = ent.get("kid")
        priv_b64 = ent.get("priv_b64")
        pub_b64 = ent.get("pub_b64")
        if not (kid and priv_b64 and pub_b64):
            continue
        mapping[kid] = _load_keypair_from_raw(kid, priv_b64, pub_b64)
    return mapping, data.get("active_kid")


def save_keystore_to_file(path: str, keystore: Dict[str, OpeKeypair], active_kid: Optional[str]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    data = export_keystore(keystore, active_kid)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(tmp, path)


def ensure_keystore_file(path: str) -> tuple[Dict[str, OpeKeypair], str]:
    """Return keystore and active kid, creating one if missing (env or fresh)."""
    ks, active = load_keystore_from_file(path)
    if ks and active in ks:
        return ks, active  # already good

    # Try env single key
    loaded = load_keypair_from_env()
    if loaded is not None:
        ks = {loaded.kid: loaded.keypair}
        active = loaded.kid
        save_keystore_to_file(path, ks, active)
        return ks, active

    # Try ODIN_KEYSTORE_JSON (multi-key keystore from env/secret)
    js = os.getenv("ODIN_KEYSTORE_JSON")
    if js:
        try:
            data = json.loads(js)
            keys_list = data.get("keys", []) or []
            env_mapping: Dict[str, OpeKeypair] = {}
            for ent in keys_list:
                kid = ent.get("kid")
                priv_b64 = ent.get("priv_b64")
                pub_b64 = ent.get("pub_b64")
                if kid and priv_b64 and pub_b64:
                    env_mapping[kid] = _load_keypair_from_raw(kid, priv_b64, pub_b64)
            # Resolve active_kid: prefer explicit field, else first with active=true, else lexicographically first
            active_kid = data.get("active_kid")
            if not active_kid:
                for ent in keys_list:
                    if ent.get("active") and ent.get("kid") in env_mapping:
                        active_kid = ent.get("kid")
                        break
            if not active_kid and env_mapping:
                active_kid = sorted(env_mapping.keys())[0]
            if env_mapping and active_kid in env_mapping:
                save_keystore_to_file(path, env_mapping, active_kid)
                return env_mapping, active_kid  # seeded from env
        except Exception:
            # Fall through to generate fresh key if env is malformed
            pass

    # Generate fresh persistent key
    kp = OpeKeypair.generate("k1")
    ks = {kp.kid: kp}
    active = kp.kid
    save_keystore_to_file(path, ks, active)
    return ks, active
