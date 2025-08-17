# ODIN — HTTP for AI (MVP scaffold)

A minimal end-to-end scaffold for ODIN: a deterministic content format (OML), cryptographic proof envelopes (OPE), and a FastAPI gateway exposing health, metrics, and a simple translate endpoint that emits OML-C + CID and an OPE proof.

## Features

- FastAPI Gateway
  - GET /health — liveness probe
  - GET /metrics — Prometheus metrics (odin_http_requests_total, odin_http_request_seconds)
  - POST /v1/echo — tiny echo
  - POST /v1/translate — builds an OML graph, persists DAG-CBOR (OML-C) to `tmp/oml/<cid>.cbor`, returns headers:
    - `X-ODIN-OML-CID` — CID of the OML-C bytes
    - `X-ODIN-OML-C-Path` — filesystem path of the persisted CBOR
    - `X-ODIN-OPE` — base64 JSON OPE envelope
    - `X-ODIN-OPE-KID` — key ID used to sign
  - POST /v1/verify — verify OPE over inline bytes or a file path (optional OML CID binding)
  - GET /v1/sft/default — expose default symbol table (JSON-hash + CBOR CID)
  - POST /v1/ledger/append, GET /v1/ledger — append-only CID ledger stub
  - OPE receipts persisted to `tmp/odin/receipts/<cid>.ope.json`
- Core library (`libs/odin_core/odin`)
  - OML deterministic normalization, DAG-CBOR encoding, CID (BLAKE3-256 base32-lower, no padding)
  - OPE (Ed25519) signing and verification over content bytes (+ optional OML CID)
  - Keystore loaders (env vars or ODIN_KEYSTORE_JSON) with active_kid support
  - JSON utilities: canonical JSON bytes (sorted keys + newline), safe parse helper
- Tests: pytest sanity + unit tests for OML, OPE, gateway integration, and JSON utils

## Quick start (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\pip.exe install -e .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn apps.gateway.api:app --host 127.0.0.1 --port 7070
```

Then:
- Health: http://127.0.0.1:7070/health
- Metrics: http://127.0.0.1:7070/metrics

POST translate example:
```json
{
  "text": "Hello",
  "source_lang": "en",
  "target_lang": "fr"
}
```

The response includes the OML CID and proof headers; the CBOR is written under `tmp/oml/`.

## OPE signing keys

The gateway loads a signing keypair via one of:

- Direct env vars:
  - `ODIN_SIGNING_KID`
  - `ODIN_SIGNING_PRIVATE_KEY_B64` (base64url, no padding)
  - `ODIN_SIGNING_PUBLIC_KEY_B64` (base64url, no padding)
- Or a JSON keystore in `ODIN_KEYSTORE_JSON` with shape:
  ```json
  {"active_kid":"k1","keys":[{"kid":"k1","priv_b64":"...","pub_b64":"...","active":true}]}
  ```

If no keys are provided, an ephemeral keypair is generated (a warning is logged when `ODIN_DEBUG=1`).

Persistent keystore:
- Set `ODIN_KEYSTORE_PATH` to persist keys across restarts (default: `tmp/odin/keystore.json`).
- `ensure_keystore_file()` will load/generate and rotate keys; the gateway signer prefers this file-backed keystore.

## Project layout

- `apps/gateway/` — FastAPI gateway app and tests
- `libs/odin_core/odin/` — core OML, OPE, keystore, and JSON utilities
- `services/` — additional services
  - `services/relay/` — relay service with SSRF defense and header policy
  - Env: `ODIN_RELAY_ALLOW_PRIVATE=1` to allow private hosts in dev; `ODIN_RELAY_RATE_LIMIT_QPS` to rate-limit requests.
- `pyproject.toml` — dependencies and pytest discovery

## Notes

- OML files are deterministic and their CID is stable across runs for the same content.
- Prometheus metrics are exposed from the same process; scrape `/metrics` to collect.
