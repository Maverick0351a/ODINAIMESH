# Work Done Log

From now on, this file will be updated after each step with a concise summary of changes and verification.

## 2025-08-17

- Core lib: OML normalize/encode + CID, OPE sign/verify, keystore loaders, JSON utils; tests added and passing.
- Gateway: FastAPI app with /health, /metrics, /v1/echo, /v1/translate; OML-C persisted to tmp/oml; OPE proof headers; metrics middleware; compat import at `apps/gateway/api.py`.
- Packaging: Root pyproject adjusted (packages=[]); editable install works; deps installed (incl. prometheus-client).
- Verification: Full pytest passed; dev server started; /health OK; /metrics served.
- Docs: README with Windows PowerShell quick-start added.

---

Next entries will be appended below, one per step.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
........                                                                                                               [100%]

$proc = Start-Process -FilePath .\.venv\Scripts\uvicorn.exe -ArgumentList "apps.gateway.api:app","--host","127.0.0.1","--port","7070" -PassThru
HEALTH: {"ok":true,"service":"gateway"}
METRICS-LEN: 1882
```

## 2025-08-17 — Step 1: OML-C + CID + Gateway wiring

- Added/updated OML symbols helper (`libs/odin_core/odin/oml/symbols.py`) with default symbol table and `sym()`/`get_default_sft()` without breaking existing Intent/Field/Rel API.
- Verified full test suite remains green.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
........                                                                                                               [100%]
```

## 2025-08-17 — Step 2: OPE over OML-C + SFT registry + Ledger stub

- Gateway translate now signs the exact OML-C bytes with OPE, binding `oml_cid`; adds `X-ODIN-OPE` and `X-ODIN-OPE-KID` headers.
- Added `/v1/sft/default` endpoint exposing the default SFT with JSON-hash and CBOR CID.
- Added append-only ledger stub: `POST /v1/ledger/append` and `GET /v1/ledger` (persists JSONL under tmp/odin/ledger/).
- Verified test suite remains green.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
.......                                                                                                                [100%]
Start-Process -NoNewWindow -FilePath .\.venv\Scripts\python.exe -ArgumentList "-m","uvicorn","apps.gateway.api:app","--host","127.0.0.1","--port","7070"
HDR OML-CID: bd4qeow3quvlutm5jgyp4lzearr6fedwi5ns5lbbjtceg6aghu4s456a
HDR OPE-KID: ephemeral
HDR OPE len: 494
```

## 2025-08-17 — Step 3: Verify endpoint + Keystore rotation + Relay stub

- Added `/v1/verify` to validate OPE over provided bytes (inline or file) with optional OML CID.
- Introduced file-backed keystore with rotation: `ensure_keystore_file` (`ODIN_KEYSTORE_PATH` override), used by gateway signer.
- Created `services/relay/api.py` with SSRF checks, strict header policy, and optional OPE verification before forwarding.
- Tests re-run: green.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
.......                                                                                                                [100%]
```

## 2025-08-17 — Step 4: Receipts persisted + Verify/Relay tests + README

- Translate now persists OPE receipts next to OML (`tmp/odin/receipts/<cid>.ope.json`).
- Added tests for `/v1/verify` and relay SSRF/header policy.
- Updated README with new endpoints, keystore persistence, and relay service.
- Test suite expanded: green.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
........                                                                                                               [100%]
```

## 2025-08-17 — Step 5: Relay hardening (rate limit + allow-private)

- Relay: added `ODIN_RELAY_ALLOW_PRIVATE` toggle, simple QPS rate limiter (`ODIN_RELAY_RATE_LIMIT_QPS`), and better error mapping (network -> 502).
- Added tests covering rate limit and allow-private behavior.
- Updated README with relay env options.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
........                                                                                                               [100%]
```
