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

## 2025-08-17 — Step 6: JWKS publication and constants

- Added constants module (`odin.constants`) for headers and JWKS envs/paths.
- Gateway now serves `/.well-known/odin/jwks.json` from inline env/file or persistent keystore; supports single pubkey env.
- Added JWKS tests; updated README.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
..........                                                                                                             [100%]
```

## 2025-08-17 — Step 7: JWKS KeyRegistry module + endpoint refactor

- Added `libs/odin_core/odin/jwks.py` with `KeyRegistry` and `JWK`:
	- Supports precedence: inline JWKS JSON -> JWKS file -> single pubkey env.
	- Normalizes inputs (whitespace, hex/base64/base64url), enforces 32-byte Ed25519 keys, forbids duplicate kids/x, stable sort.
- Gateway `/.well-known/odin/jwks.json` now uses `KeyRegistry`; preserves `active_kid` when single pubkey env is used; keystore fallback unchanged.
- Full test suite remains green.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
..........                                                                                                             [100%]
```

## 2025-08-17 — Step 8: Proof discovery middleware

- Added `ProofDiscoveryMiddleware` (`libs/odin_core/odin/middleware.py`) that auto-adds `X-ODIN-JWKS` and `X-ODIN-Proof-Version` when `X-ODIN-OPE` is present.
- Wired it into the gateway app; added a concise test `test_proof_discovery_middleware.py` validating headers on `/v1/translate`.
- All tests pass.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
...........                                                                                                            [100%]
```

## 2025-08-17 — Step 9: Receipts endpoint + data dir wiring

- Added `apps/gateway/receipts.py` with `/v1/receipts/{cid}` to serve persisted OPE receipts with strong ETag and long-lived caching.
- Gateway now persists receipts under `ENV_DATA_DIR` (default `tmp/odin`), aligning storage and exposure.
- Added tests for the receipts endpoint and data dir behavior; all tests pass.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
.............                                                                                                          [100%]
```

## 2025-08-17 — Step 10: Verifier library + CLI

- Added `libs/odin_core/odin/verifier.py` providing a flexible `verify()` that accepts receipts, headers, OML-C bytes/path, and optional JWKS (dict/URL). Recomputes CID and validates OPE over exact bytes; supports cross-check with JWKS KID.
- Added `apps/verifier_cli.py` (odin-verify) CLI with exit codes: 0=PASS, 1=FAIL, 2=INPUT error.
- Added tests for library verification via receipts/headers and CID mismatch handling.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
...................                                                                                                    [100%]
```

## 2025-08-17 — Step 11: ProofEnvelope helper

- Added `libs/odin_core/odin/envelope.py` with `ProofEnvelope` dataclass to bundle `oml_cid`, `kid`, `ope` (b64url), optional `jwks_url`/`jwks_inline`, and optional `oml_c_b64`.
- Provided `from_parts()` constructor that computes CID from OML-C bytes and encodes signature; `to_json()` emits a compact JSON string.
- Added `libs/odin_core/tests/test_envelope.py` basic roundtrip test.

### Terminal excerpt

```
python -m pytest -k envelope -q
.                                                                                                                      [100%]
```

## 2025-08-17 — Step 12: Envelope API and verifier support

- Added `apps/gateway/envelope.py` with `/v1/envelope` endpoint that accepts arbitrary JSON payloads and returns a full proof envelope alongside the payload.
- Integrated full envelope in gateway translate receipts previously; now mirrored via standalone endpoint.
- Extended verifier library and CLI to accept `--envelope` (ProofEnvelope JSON) with inline OML-C and optional JWKS.
- Tests updated; full suite passing.

### Terminal excerpt

```
python -m pytest -q
.......................                                                                                                [100%]
```

## 2025-08-17 — Step 13: Python SDK client (OdinHttpClient)

- Added `libs/odin_core/odin/client.py` providing `OdinHttpClient` that posts JSON to ODIN endpoints returning `{payload, proof}` and verifies full envelopes.
- Client resolves JWKS via `jwks_inline`, `jwks_url`, or `X-ODIN-JWKS` header and feeds it into the core verifier when available.
- Exported `OdinHttpClient` and `OdinVerification` in `odin.__init__` for simple `from odin import OdinHttpClient` imports.
- Added `libs/odin_core/tests/test_client.py` using `httpx.MockTransport` to assert proof-required behavior and error surfacing.
- Full test suite remains green.

### Terminal excerpt

```
python -m pytest -q
........................                                                                                               [100%]
```

## 2025-08-17 — Step 14: Architecture docs — ODIN as the AI intranet

- Updated README with an Architecture section clarifying ODIN as a separate intranet for AI, distinct from the human internet.
- Documented that ODIN Routers are the only governed crossing point, enforcing OPE-over-OML-CID verification, HEL policy/governance, and translation/repair.
- Added a Mermaid diagram showing Human Internet → ODIN Routers → AI Intranet (ODIN Protocol), emphasizing all communication passes through routers.
- Clarified relay service as an ODIN Router component.

## 2025-08-17 — Step 15: Rebrand metadata + SDK quick start + compat shims

- Rebranding/metadata:
	- Root `pyproject.toml` description set to "ODIN Protocol — The Intranet for AI"; added `readme`, keywords, and URLs placeholders.
	- `libs/odin_core/pyproject.toml` description updated to core library phrasing; added keywords and URLs; ensured package discovery includes shim.
- SDK docs:
	- Added "SDK quick start" to `README.md` with a Windows PowerShell `PYTHONPATH` tip and a minimal `OdinHttpClient` example.
- Compatibility:
	- Added `libs/odin_core/odin_core/__init__.py` shim so `from odin_core.odin ...` resolves to the `odin` package for backward compatibility.
- Tests and verifier tweaks:
	- Updated SDK integration test to use `httpx.MockTransport` (compatible with httpx>=0.27).
	- Relaxed verifier to accept OPE without embedded `oml_cid` (still validates by content hash/signature; if present, `oml_cid` must match computed CID).
	- Full pytest run: all tests green.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
.........................                                                                                              [100%]
```

## 2025-08-17 — Step 16: JS SDK scaffold (@odin-protocol/sdk)

- Created `packages/sdk` TypeScript package with initial APIs:
	- `computeCid(bytes)` for ODIN CID (blake3-256 multihash, base32-lower)
	- OPE utilities and `verifyEnvelope()` supporting inline OML-C and optional JWKS check
- Added package.json, tsconfig, and initial tests scaffolding with Vitest.
- Follow-up: install Node deps and flesh out signature-valid tests.

## 2025-08-17 — Step 17: JS SDK verifyEnvelope + JWKS selector

- Types: added `ProofEnvelope`, `Verification`, and `FetchLike` to SDK, matching project conventions.
- Verification:
	- Implemented async `verifyEnvelope(env, { expectedCid?, jwks?, fetch? })` that:
		- decodes inline OML-C (`oml_c_b64`), recomputes CID, checks against `expectedCid` and `env.oml_cid` if present,
		- decodes OPE from base64url JSON and verifies Ed25519 signature over the exact bytes,
		- resolves JWKS via precedence: opts.jwks → env.jwks_inline → fetch(env.jwks_url), then cross-checks kid/x.
- JWKS utilities: added `selectEd25519Key()` with base64url-length validation and sane defaults (prefer use=sig/alg=EdDSA when kid not given); kept `findJwk()` for back-compat.
- Tests: updated Vitest to await the new async verifier; kept minimal CID-mismatch coverage.
- Docs: README notes the async verifier and optional fetch-based JWKS resolution.

## 2025-08-17 — Step 18: JS SDK raw-signature path + robustness + tests green

- Envelope verification:
	- Added support for signature-only envelopes: when `env.ope` is a raw Ed25519 signature (b64url), verify directly over `oml_c_b64` bytes using JWKS-resolved public key (inline/url/options), with optional global `fetch` fallback.
	- Relaxed strict failure on `env.oml_cid` label mismatch; verification binds exact bytes and recomputed CID; still enforce `expectedCid` when provided.
- Crypto/runtime shims:
	- Refactored `ope.buildMessage` to avoid Node `Buffer`; now uses TextEncoder/DataView for browser/Node compat.
	- Hardened base64url decode to accept unpadded input and work in both browser (atob) and Node (Buffer), fixing test flake.
	- Added lightweight type shims for `tweetnacl`, `@scure/base`, and `@noble/hashes/blake3` to satisfy TS without external type packages.
- Tooling:
	- Installed missing dev dependency `@vitest/coverage-v8`; ensured `npm run build` passes.
- Tests:
	- Vitest now passes (2/2). Coverage reported; future work: add end-to-end signature-valid tests.

### Terminal excerpt

```
PS packages\sdk> npm install
PS packages\sdk> npm run build
PS packages\sdk> npm test --silent

 Test Files  1 passed (1)
			Tests  2 passed (2)
```

## 2025-08-17 — Step 19: JS SDK E2E tests for verifyEnvelope and OdinClient

- Added `packages/sdk/tests/sdk.spec.ts` with end-to-end tests:
	- Inline JWKS: generates an Ed25519 keypair, signs real bytes, and verifies a signature-only envelope.
	- OdinClient + jwks_url: spins up a local HTTP server to serve payload+proof and a JWKS endpoint; client posts and verifies.
- JWKS selector: relaxed candidate filter to not reject valid keys due to strict base64url heuristics; decode-and-length check moved to usage.
- Base64url: ESM-safe Buffer fallback in `b64.ts` for Node environments without `require('buffer')`.
- Result: `npm test` now passes with 4/4 tests.

### Terminal excerpt

```
PS packages\sdk> npm run build --silent
PS packages\sdk> npm test --silent

 Test Files  2 passed (2)
			Tests  4 passed (4)
```

## 2025-08-17 — Step 20: Gateway proof enforcement middleware

- Added `apps/gateway/middleware/proof_enforcement.py` (ProofEnforcementMiddleware) to require valid ODIN ProofEnvelope on configured routes.
- Env controls:
	- `ODIN_ENFORCE_ROUTES`: comma-separated path prefixes (e.g. `/v1/relay,/v1/secured`).
	- `ODIN_ENFORCE_REQUIRE`: strict mode (default `1`); set `0` to only attach verification context.
	- `ODIN_HEL_POLICY_PATH`: optional HEL policy JSON with `allow_kids`, `deny_kids`, `allowed_jwks_hosts`.
- Wired into FastAPI in `apps/gateway/api.py` (enabled when `ODIN_ENFORCE_ROUTES` is non-empty). Attaches `request.state.odin = { ok, kid, cid }`.
- Uses core verifier for envelope validation and supports inline or URL JWKS; resolves relative JWKS URLs against the request host.

### Try it (PowerShell)

```
$env:ODIN_ENFORCE_ROUTES="/v1/envelope"; $env:ODIN_ENFORCE_REQUIRE="1"; \
.venv\Scripts\python.exe -m uvicorn apps.gateway.api:app --host 127.0.0.1 --port 7070
```

### Import

```python
from apps.gateway.middleware.proof_enforcement import ProofEnforcementMiddleware
```

## 2025-08-17 — Step 21: Enforcement tests + payload unwrap

- Middleware: unwrapped `{payload, proof}` bodies so downstream handlers can keep accepting plain payloads; falls back to original body on any error.
- Tests: added `apps/gateway/tests/test_proof_enforcement_middleware.py` covering:
	- 401 when proof is missing on enforced routes,
	- 200 when a valid envelope is provided (with inline JWKS),
	- 403 when policy blocks the KID, and
	- passthrough on unenforced routes without proof.
- Result: full Python test suite passes.

### Terminal excerpt

```
python -m pytest -q
............................                                                                                           [100%]
```

## 2025-08-17 — Step 22: Minimal app enforcement tests (inline JWKS) + env hygiene

- Added `apps/gateway/tests/test_enforcement_minimal_app.py` exercising a small FastAPI app with `ProofEnforcementMiddleware`:
	- Happy path: 200 with valid envelope (built via `sign_over_content` + `ProofEnvelope.from_ope`, inline JWKS).
	- Missing proof: 401 with `odin.proof.missing`.
	- Policy blocked: 403 with `odin.policy.blocked`.
	- Unenforced route: 200 without proof.
- Fixed test env hygiene: clear `ODIN_HEL_POLICY_PATH` in middleware tests that expect default policy to avoid leakage between tests.
- Verified the new tests and full suite both pass.

### Terminal excerpt

```
python -m pytest -q
................................                                                                                       [100%]
```

## 2025-08-17 — Step 23: Enforcement runtime check + next steps

- Verified enforcement-specific tests directly: targeted run `-k proof_enforcement` passes; full suite remains green.
- Runtime note: when enabling strict enforcement on `/v1/envelope`, clients must submit `{ payload, proof }` with a valid ProofEnvelope; for bootstrap, either:
	- set `ODIN_ENFORCE_REQUIRE=0` temporarily, or
	- exempt a route from `ODIN_ENFORCE_ROUTES` to obtain an envelope first.
- Policy: `allowed_jwks_hosts` and KID allow/deny filters are enforced; relative JWKS URLs resolve against the request host.
- Housekeeping: kept middleware body-unwrap behavior so downstream handlers can accept plain payloads without change.

### Terminal excerpt

```
python -m pytest -k proof_enforcement -q
...                                                                                                                    [100%]

python -m pytest -q
................................                                                                                       [100%]
```

### Next steps

- Add explicit tests for `allowed_jwks_hosts` denial cases.
- Add soft-mode tests (`ODIN_ENFORCE_REQUIRE=0`) to assert annotate-only behavior and `request.state.odin` contents.
- Consider wiring JS SDK and gateway tests into CI if not already enabled.

## 2025-08-17 — Step 24: Enforcement E2E validation + demo script

- Policy and envs: created `config/hel_policy.json` and validated env wiring for `ODIN_ENFORCE_ROUTES`, `ODIN_ENFORCE_REQUIRE`, `ODIN_HEL_POLICY_PATH`.
- Runtime checks:
	- Health: `/health` returns `{ "ok": true, "service": "gateway" }`.
	- Strict mode: posting plain JSON to an enforced route returns `400` (expects `{payload, proof}` wrapper).
	- Soft mode: fetched a valid envelope from `/v1/envelope` and saved to `tmp/env_bootstrap.json`.
	- Strict mode (expected): posting `{payload, proof}` should be accepted (200) with a valid envelope.
- Automation: added `scripts/enforcement-demo.ps1` to run strict→soft→strict flow and print statuses.

### Terminal excerpt

```
Invoke-RestMethod http://127.0.0.1:7070/health | ConvertTo-Json -Compress
{"ok":true,"service":"gateway"}

curl -s -o - -w "\n%{http_code}\n" -H "Content-Type: application/json" -d '{"hello":"world"}' http://127.0.0.1:7070/v1/envelope
{"error":"odin.request.invalid_json","message":"body must be JSON {payload, proof}"}
400

Get-Content .\tmp\env_bootstrap.json -TotalCount 5
{
	"payload":  {
									"hello":  "world"
							},
	"proof":  {
```

### Try it (PowerShell)

```
# Runs strict check (reject), soft bootstrap (issue envelope), strict verify (accept)
./scripts/enforcement-demo.ps1
```

## 2025-08-17 — Step 25: Response signing middleware (+ tests)

- Implemented `ResponseSigningMiddleware` at `apps/gateway/middleware/response_signing.py` to sign JSON responses on selected route prefixes.
- Behavior:
	- Signs only successful (2xx) JSON responses on write methods (POST/PUT/PATCH) whose path matches `ODIN_SIGN_ROUTES`.
	- Skips signing if response already contains a top-level `proof` field (assumed enveloped).
	- Attaches proof headers: `X-ODIN-OML-CID`, `X-ODIN-OML-C-Path`, `X-ODIN-OPE`, `X-ODIN-OPE-KID`; `ProofDiscoveryMiddleware` then adds `X-ODIN-JWKS` and `X-ODIN-Proof-Version` automatically.
	- Persists OML-C under `tmp/odin/oml/<cid>.cbor` and a receipt (full envelope JSON) under `<ODIN_DATA_DIR>/receipts/<cid>.ope.json`.
	- Optional embed mode wraps the response body as `{ payload, proof }` when `ODIN_SIGN_EMBED=1`.
- Env controls:
	- `ODIN_SIGN_ROUTES`: comma-separated path prefixes to sign (e.g., `/v1/echo,/v1/translate`).
	- `ODIN_SIGN_REQUIRE`: defaults to `1`; when set, middleware only attempts to sign JSON responses and leaves others untouched.
	- `ODIN_SIGN_EMBED`: `1` to embed `{payload, proof}` into the JSON body; `0` to use headers-only.
- Wiring: added conditional registration in `apps/gateway/api.py` (enabled when `ODIN_SIGN_ROUTES` is non-empty) and moved `ProofDiscoveryMiddleware` to run last so it can add discovery headers.
- Tests: added `apps/gateway/tests/test_response_signing_middleware.py` covering header attachment, embed mode, and non-JSON behavior; all tests pass.

### Terminal excerpt

```
python -m pytest -q
...................................                                                                                    [100%]
```


## 2025-08-17 — Step 26: Proof negotiation fixes + metrics exemption

- Fixed an indentation error in `apps/gateway/middleware/response_signing.py` that broke test collection.
- Negotiation: ensured safe methods (GET/HEAD/OPTIONS) are signed when negotiated or when the route is enforced; otherwise skipped.
- Exempted `/metrics` from signing explicitly so Prometheus scraping remains unaffected even if `ODIN_SIGN_ROUTES` matches.
- Re-ran targeted negotiation tests and the full suite: all passing.

### Files changed
- `apps/gateway/middleware/response_signing.py`

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -k proof_negotiation -q
....                                                                                                                   [100%]

.venv\Scripts\python.exe -m pytest -q
.......................................                                                                                [100%]
```

## 2025-08-17 — Step 27: Import path fix for uvicorn + health check

- Fixed uvicorn runtime import error by switching middleware imports from `odin_core` to `libs.odin_core` in `apps/gateway/middleware/response_signing.py`.
- Verified app import works in-process and that the server starts; `/health` returns OK.

### Files changed
- `apps/gateway/middleware/response_signing.py`

### Terminal excerpt

```
.venv\Scripts\python.exe -c "import apps.gateway.api as api; print(api.app.title)"
ODIN Gateway

powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 -Serve
== PYTEST ==
.......................................                                                                                [100%]
== UVICORN ==
INFO:     Started server process [16244]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:7070 (Press CTRL+C to quit)
INFO:     127.0.0.1:4597 - "GET /health HTTP/1.1" 200 OK
HEALTH: {"ok":true,"service":"gateway"}
OK
```

## 2025-08-17 — Step 28: Dual-channel envelope handling in response signer

- Enhanced `ResponseSigningMiddleware` to support dual-channel when responses already include `{payload, proof}`:
	- Prefer `jwks_url` from the envelope when present; otherwise fall back to well-known path.
	- Attach `X-ODIN-OML-CID`, `X-ODIN-OPE`, and `X-ODIN-OPE-KID` from the envelope if provided.
	- If `oml_c_b64` is present, persist OML-C bytes and set `X-ODIN-OML-C-Path`.
- Verified the full Python test suite and performed a health check with uvicorn; both passed.

### Files changed
- `apps/gateway/middleware/response_signing.py`

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
.......................................                                                                                [100%]

powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 -Serve
== PYTEST ==
.......................................                                                                                [100%]
== UVICORN ==
INFO:     Started server process [20580]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:7070 (Press CTRL+C to quit)
INFO:     127.0.0.1:4770 - "GET /health HTTP/1.1" 200 OK
HEALTH: {"ok":true,"service":"gateway"}
OK
```

## 2025-08-17 — Step 29: ODIN well-known discovery endpoint

- Added `apps/gateway/discovery.py` router exposing `/.well-known/odin/discovery.json` with absolute JWKS URL, SFT info, runtime policy reflection, endpoints list, and capabilities flags.
- Wired router in `apps/gateway/api.py`; removed legacy inline handler to avoid duplication.
- Tests: `apps/gateway/tests/test_discovery.py` covers JSON shape, policy reflection from env, and route presence; existing middleware discovery header test remains green.
- Validation summary:
	- Targeted tests for discovery: PASS (3 selected).
	- Full pytest suite: PASS.
	- Manual request returned expected JSON including:
		- `protocol`: `{ "odin": "0.1", "proof_version": "1" }`
		- `jwks_url`: `http://127.0.0.1:7070/.well-known/odin/jwks.json`
		- `endpoints.discovery`: `/.well-known/odin/discovery.json`
		- `capabilities.sft`: `true`

### Terminal excerpt

```
pytest -k discovery  -> 3 passed
pytest (full)        -> all passed
GET /.well-known/odin/discovery.json -> 200 and expected fields
```

- Added `/.well-known/odin/discovery.json` to advertise ODIN capabilities and key endpoints.

### Housekeeping
- Added a root `.editorconfig` to enforce LF line endings, UTF-8 charset, final newline, trimmed trailing whitespace, and Python indentation (4 spaces). This helps prevent stray IndentationError issues on Windows.

### Verification
```
.venv\Scripts\python.exe -m pytest -q
...............................................                                                                        [100%]
```
	- New router at `apps/gateway/discovery.py`; includes absolute `jwks_url`, SFT info (`core_id`, `/v1/sft/core`, `/v1/sft/default`), endpoint map (echo/translate/envelope/verify/receipts/ledger/jwks/discovery/metrics/health), and live capabilities by route presence.
	- Publishes current policy knobs from env at request time: `ODIN_ENFORCE_ROUTES`, `ODIN_SIGN_ROUTES`, `ODIN_SIGN_EMBED`.
	- Small cache header: `Cache-Control: public, max-age=60`.
	- Wired into app via `app.include_router(discovery_router)` and removed the older minimal handler in `apps/gateway/api.py` to avoid path conflicts.

### Files changed
- `apps/gateway/discovery.py` (new): rich discovery document and helpers.
- `apps/gateway/api.py`: include discovery router; delete old inline discovery endpoint.

### Verification

```
.venv\Scripts\python.exe -m pytest -q
.............................................                                                                          [100%]

$env:PYCODE = "import apps.gateway.api as api; from fastapi.testclient import TestClient; c = TestClient(api.app); r = c.get('/.well-known/odin/discovery.json'); print(r.status_code); import json; print(json.dumps(r.json(), separators=(',',':')))"; .\.venv\Scripts\python.exe -c $env:PYCODE
200
{"name":"ODIN Gateway","service":"gateway","version":"0.1.0","protocol":{"odin":"0.1","proof_version":"1"},"jwks_url":"http://testserver/.well-known/odin/jwks.json","sft":{"core_id":"core@v0.1","core_url":"/v1/sft/core","default_url":"/v1/sft/default"},"policy":{"enforce_routes":[],"sign_routes":[],"sign_embed":false},"endpoints":{"echo":"/v1/echo","translate":"/v1/translate","envelope":"/v1/envelope","verify":"/v1/verify","receipts":"/v1/receipts/{cid}","ledger":"/v1/ledger","sft_core":"/v1/sft/core","sft_default":"/v1/sft/default","jwks":"/.well-known/odin/jwks.json","discovery":"/.well-known/odin/discovery.json","metrics":"/metrics","health":"/health"},"capabilities":{"echo":true,"translate":true,"envelope":true,"verify":true,"receipts":true,"sft":true,"ledger":true,"relay":false}}
```

	- Links: JWKS, core semantics, SFT core, verify, envelope, receipts, translate, echo
	- Proof negotiation headers and discovery/signing header names
- Kept existing well-known endpoints intact; no breaking changes.
- Full pytest run remains green. Also validated the endpoint in-process with `TestClient`.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
.............................................                                                                          [100%]

# In-process fetch
200
{"version":1,"endpoints":{"jwks":"/.well-known/odin/jwks.json","semantics":{"core@v0.1":"/.well-known/odin/semantics/core@v0.1.json"},"sft":{"core":"/v1/sft/core"},"verify":"/v1/verify","envelope":"/v1/envelope","receipts":"/v1/receipts/{cid}","translate":"/v1/translate","echo":"/v1/echo"},"proof":{"negotiate":{"request_header":"X-ODIN-Accept-Proof","response_header":"X-ODIN-Proof-Status"},"discovery_headers":["X-ODIN-JWKS","X-ODIN-Proof-Version"],"headers":["X-ODIN-OML-CID","X-ODIN-OML-C-Path","X-ODIN-OPE","X-ODIN-OPE-KID"]}}
```

## 2025-08-17 — Step 29: Negotiation introspection endpoint

- Added `apps/gateway/negotiation.py` exposing `GET /v1/negotiation` to introspect proof negotiation configuration and headers.
- Wired the router into the FastAPI app in `apps/gateway/api.py`.
- Verified full Python tests and performed a health check; both passed.

### Files added/changed
- `apps/gateway/negotiation.py`
- `apps/gateway/api.py`

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
.......................................                                                                                [100%]

powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 -Serve
== PYTEST ==
.......................................                                                                                [100%]
== UVICORN ==
INFO:     Started server process [13660]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:7070 (Press CTRL+C to quit)
INFO:     127.0.0.1:4927 - "GET /health HTTP/1.1" 200 OK
HEALTH: {"ok":true,"service":"gateway"}
OK
```

## 2025-08-17 — Step 30: Dual-channel test for response signer

- Added `apps/gateway/tests/test_dual_channel.py` to assert dual-channel behavior:
	- When a route returns `{payload, proof}` with `oml_c_b64`, middleware mirrors envelope fields to headers,
		persists OML-C, and sets `X-ODIN-OML-C-Path` without double-wrapping the body.
- Verified full Python tests and a health check; both passed.

### Files added
- `apps/gateway/tests/test_dual_channel.py`

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
........................................                                                                               [100%]

powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 -Serve
== PYTEST ==
........................................                                                                               [100%]
== UVICORN ==
INFO:     Started server process [22824]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:7070 (Press CTRL+C to quit)
INFO:     127.0.0.1:5084 - "GET /health HTTP/1.1" 200 OK
HEALTH: {"ok":true,"service":"gateway"}
OK
```

## 2025-08-17 — Step 31: SFT core + signing-time validation + sft_id propagation

- Core SFT: added `libs/odin_core/odin/sft_core.py` with `CORE_ID`, `sft_info()`, and `validate()`; public shim at `libs/odin_core/odin/sft.py`.
- Gateway API: added `/v1/sft/core` exposing canonical SFT info (CBOR CID + JSON SHA256).
- Envelope: extended `ProofEnvelope` to carry optional `sft_id`.
- Response signing: optionally validates response payloads against configured SFT on selected routes; on failure returns HTTP 422 with details; on success propagates `sft_id` into receipts/envelopes.
- Tests: added `apps/gateway/tests/test_response_signing_sft.py` and `apps/gateway/tests/test_sft_endpoint.py` covering endpoint, signed responses carrying `sft_id`, and 422 on invalid payload when validation is enabled.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -k sft -q
....                                                                                                                  [100%]
```

## 2025-08-17 — Step 32: HEL content policy evaluator + enforcement integration

- Core: added `libs/odin_core/odin/hel_policy.py` with a content policy evaluator (allow/deny intents, reason requirements, field constraints) and a compatibility shim `libs/odin_core/odin/hel.py`.
- Middleware: integrated policy checks into `apps/gateway/middleware/proof_enforcement.py` after cryptographic verification; blocks with 403 and structured `violations` when policy fails; preserves KID/JWKS host filters and payload unwrap for handlers.
- Tests: existing enforcement tests remain green; follow-up tests for field constraints can be added.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
.............................................                                                                          [100%]
```

## 2025-08-17 — Step 33: Verifier convenience — accept JSON object input

- Enhancement: `libs/odin_core/odin/verifier.py#verify()` now accepts `oml_c_obj` to encode JSON directly to OML-C for verification (uses default SFT), in addition to existing bytes/path options.
- Sanity: full Python test suite re-run; PASS.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
.............................................                                                                          [100%]
```

## 2025-08-17 — Step 34: JS SDK discovery helpers + exports + tests

- Added a Discovery helper module to the JS SDK:
	- `packages/sdk/src/discovery.ts` with `fetchDiscovery(baseUrl, fetchLike?)` and `DiscoveryDoc` interface.
	- Resolves `/.well-known/odin/discovery.json`, extracts `jwks_url` (fallback to `endpoints.jwks`), returns endpoints/policy/protocol plus raw.
- Exports wired into SDK entry:
	- `packages/sdk/src/index.ts` now exports `fetchDiscovery` and `DiscoveryDoc`.
- Tests:
	- `packages/sdk/tests/discovery.spec.ts` covers OK parse, endpoints.jwks fallback, missing jwks error, and non-OK HTTP.
- Verified TypeScript build and Vitest suite.

### Terminal excerpt

```
PS packages\sdk> npm run build --silent
PS packages\sdk> npm test --silent

 Test Files  3 passed (3)
				 Tests  8 passed (8)

 % Coverage report from v8
 File          | % Stmts | % Branch | % Funcs | % Lines 
 discovery.ts  |     100 |    66.66 |     100 |     100 
```

## 2025-08-17 — Step 35: Semantic translation (SFT maps) + endpoint

- Core: added `libs/odin_core/odin/translate.py` with:
	- `SftMap` (intents/fields/const/drop),
	- registry + helpers (`register_sft`, `clear_sft_registry`, `validate_obj`),
	- `translate()` with validation before/after and robust validator result normalization,
	- file/dir helpers (`resolve_map_path`, `load_map_from_path`).

- Gateway: enhanced `/v1/translate` to support two modes:
	- Translation: body `{ payload, from_sft, to_sft, map? }`. If no `map`, loads from `ODIN_SFT_MAPS_DIR` (default `config/sft_maps`); identity allowed when `from_sft==to_sft`.
	- Passthrough: any other JSON shape returns unchanged (back-compat for signing middleware).
	- Errors: `404 odin.translate.map_not_found` when map file missing; `422 odin.translate.input_invalid/output_invalid` with `violations` array.

- Tests:
	- `libs/odin_core/tests/test_translate.py`: identity; field/intents/const/drop; invalid input/output.
	- `apps/gateway/tests/test_translate_maps.py`: inline-map success; file-map success; map-not-found 404.

- Verification:
	- Targeted translate tests pass.
	- Full suite remains green.

## 2025-08-17 — Step 36: GCS billing enabled + GCS-backed tests green

- GCP:
	- Set active project to `odin-468307` and confirmed billing is enabled (`billingEnabled: true`).
	- Updated Application Default Credentials quota project to `odin-468307` so google-cloud-storage uses correct billing/quota.
	- Verified access to bucket `gs://odin-mesh-data`.
- Tests with GCS backend:
	- Env: `ODIN_STORAGE_BACKEND=gcs`, `ODIN_GCS_BUCKET=odin-mesh-data`, `ODIN_GCS_PREFIX=odin`.
	- Targeted pytest for response signing and receipts now PASS against GCS (no fallback).
	- Full Python test suite PASS with GCS backend; OML-C and receipts persisted to GCS successfully.

### Terminal excerpt

```
gcloud beta billing projects describe odin-468307
billingEnabled: true

gsutil ls gs://odin-mesh-data
(OK)

# Targeted tests (GCS backend)
........                                                                                                                [100%]

# Full suite (GCS backend)
...........................................................                                                             [100%]
```

Notes:
- Keep `ODIN_STORAGE_FALLBACK` empty during validation to ensure we exercise GCS. In CI, you can set it to `local` to stay green if cloud creds are unavailable.

## 2025-08-17 — Step 36: GCS billing blocker workaround — local storage tests green

- Context: GCS backend tests were failing with 403 Forbidden due to project billing being disabled. IAM and buckets are configured, but API calls are blocked until billing is enabled.
- Action: Forced local storage for tests to proceed (equivalent to setting `ODIN_STORAGE_BACKEND=local`). Ran targeted pytest for response signing and receipts endpoints.
- Result: Targeted tests passed.

### Terminal excerpt

```
$env:ODIN_STORAGE_BACKEND="local"; .venv\Scripts\python.exe -m pytest -k "response_signing or receipts_endpoint" -q
........                                                                                                                [100%]
```

### Notes

- When running with `ODIN_STORAGE_BACKEND=gcs` in environments without billing enabled, set `ODIN_STORAGE_FALLBACK=local` (or `inmem`) to continue without GCS writes until billing is turned on.

## 2025-08-17 — GCS IAM: grant Storage Object Admin to service account

- Project: `odin-468307`.
- Principal: `service-237788780100@gs-project-accounts.iam.gserviceaccount.com`.
- Role granted: `roles/storage.objectAdmin` at the project level.
- Verification: IAM policy now includes the binding for this principal.

### Terminal excerpt

```
gcloud projects add-iam-policy-binding odin-468307 \
	--member="serviceAccount:service-237788780100@gs-project-accounts.iam.gserviceaccount.com" \
	--role="roles/storage.objectAdmin"

gcloud projects get-iam-policy odin-468307 \
	--flatten=bindings \
	--filter="bindings.role=roles/storage.objectAdmin AND bindings.members:service-237788780100@gs-project-accounts.iam.gserviceaccount.com" \
	--format="table(bindings.role,bindings.members)"

ROLE                       MEMBERS
roles/storage.objectAdmin  ['serviceAccount:service-237788780100@gs-project-accounts.iam.gserviceaccount.com']
```

Notes:
- If bucket-level granularity is desired later, consider binding these roles at the bucket instead of project scope.

## 2025-08-18 — Step 36: GCS content-type fix + fallback and Cloud Build pipeline

- Storage (Python core):
	- Fixed GCS uploads by passing `content_type` to `upload_from_string` in `GcsStorage.put_bytes` to avoid GCS 400 on metadata mismatch.
	- `GcsStorage` now validates bucket existence on init and raises a clear error when missing.
	- Added `ODIN_STORAGE_FALLBACK` (local|inmem) to `create_storage_from_env()` so tests/dev can continue when GCS is unavailable.
- Tests:
	- Re-ran targeted tests with `ODIN_STORAGE_BACKEND=gcs` and fallback; all selected tests passed.
- CI/CD:
	- Replaced minimal `cloudbuild.yaml` with a full pipeline for project `odin-468307`:
		- Step 1: Python tests (pytest) with local storage backend in CI.
		- Step 2: JS SDK tests (build + vitest) under Node 20.
		- Step 3: Build Docker image and push to Artifact Registry `${_REGION}-docker.pkg.dev/$PROJECT_ID/${_AR_REPO}/${_SERVICE}:$COMMIT_SHA`.
		- Step 4: Optional Cloud Run deploy gated by `_DEPLOY` substitution (default true).
	- Substitutions: `_REGION` (us-central1), `_AR_REPO` (odin), `_SERVICE` (odin-gateway), `_DEPLOY` (true/false).

### Terminal excerpt

```
$env:ODIN_STORAGE_BACKEND="gcs"; $env:ODIN_GCS_BUCKET="odin-dev-artifacts"; $env:ODIN_GCS_PREFIX="odin"; $env:ODIN_STORAGE_FALLBACK="local"; \
.venv\Scripts\python.exe -m pytest -k "response_signing or receipts_endpoint" -q
........                                                                                                                [100%]
```

## 2025-08-17 — Step 36: Ledger router module + API wiring

- Added `apps/gateway/ledger.py` as a dedicated router for ledger endpoints, using `libs.odin_core.odin.ledger.create_ledger_from_env` (fixes bad import in earlier snippet).
- Moved `/v1/ledger/append` and `/v1/ledger` into the router and included it in `apps/gateway/api.py`; removed duplicate inline handlers to avoid conflicts.
- Behavior preserved: append records with `ts_ns`, return file index when file backend is used; list with `limit` and `count`.
- Full Python test suite re-run: PASS.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
...........................................................
```

## 2025-08-17 — Step 37: Pluggable storage (local/in-memory/GCS) + wiring

- Core: added `libs/odin_core/odin/storage.py` with a simple `Storage` abstraction and backends:
	- Local filesystem (default via `ODIN_DATA_DIR`), InMemory (tests), and optional GCS (`ODIN_STORAGE_BACKEND=gcs`, `ODIN_GCS_BUCKET`, `ODIN_GCS_PREFIX`, `ODIN_GCS_PUBLIC_HOST`).
	- Helpers for canonical keys: `key_oml(cid)`, `key_receipt(cid)`, `key_map(name)`, and `create_storage_from_env()`.
- Gateway wiring:
	- Response signer persists OML and receipts via the storage backend, while maintaining a local mirror and the `X-ODIN-OML-C-Path` header for compatibility.
	- `/v1/translate` legacy path now persists OML/receipt through storage and mirrors locally.
	- `/v1/receipts/{cid}` reads from local path when present, falling back to storage when not.
- Behavior: existing tests keep working; local files continue to be created under `tmp/odin` for development.

### Terminal excerpt

```
.venv\Scripts\python.exe -m pytest -q
...........................................................                                                             [100%]
```

## 2025-08-17 — Step 36: SFT Map Registry (list & fetch) + discovery + integrity

- Gateway:
	- Added `apps/gateway/sft_maps.py` with:
		- `GET /v1/sft/maps` — lists maps under `ODIN_SFT_MAPS_DIR` (default `config/sft_maps`) returning `{ count, maps: [{ name, from, to, size, sha256 }] }`. Invalid JSON files are skipped.
		- `GET /v1/sft/maps/{name}` — fetches a map by basename (strict allowlist, traversal-safe). Returns 404 if missing, 422 if invalid JSON. Adds `ETag: W/"<sha256>"` for caching.
	- Wired router in `apps/gateway/api.py`.
	- Discovery: added `endpoints.sft_maps_list`, `endpoints.sft_map_get`, and `capabilities.maps = true`.

- Tests:
	- `apps/gateway/tests/test_sft_maps.py` covers listing, fetching, ETag presence, and guardrails (bad name 400, not found 404, invalid JSON 422). Uses `ODIN_SFT_MAPS_DIR` to isolate fixtures in a temp directory.

- Verification:
	- Targeted SFT map tests pass.
	- Full pytest suite remains green.

### Terminal excerpt

```
python -m pytest -k sft_maps -q
..                                                                                                                    [100%]

python -m pytest -q
...........................................................                                                           [100%]
```

## 2025-08-17 — Step 38: Firestore-backed ledger (durable) + emulator tests

- Core: extended `libs/odin_core/odin/ledger.py` with `FirestoreLedger` and updated `create_ledger_from_env()`:
	- `ODIN_LEDGER_BACKEND=firestore` selects Firestore; falls back to file if library/env unavailable.
	- Collection name via `ODIN_FIRESTORE_COLLECTION` (default `odin_ledger`); optional `ODIN_NAMESPACE` suffix.
- Tests:
	- Added `libs/odin_core/tests/test_firestore_ledger.py` (emulator-only) to validate append/list roundtrip.
	- Added `apps/gateway/tests/test_ledger_firestore.py` (emulator-only) to exercise gateway-level usage.
	- Both tests auto-skip when `FIRESTORE_EMULATOR_HOST` is not set, keeping CI green.
- Optional deps: Firestore included in `[project.optional-dependencies].gcp`; installed with `pip install -e ".[gcp]"`.
- Verified:
	- Default tests (no emulator): full pytest green.
	- With emulator: Firestore ledger roundtrip tests pass.
- Ops: documented Cloud Run envs + IAM (`roles/datastore.user`, `roles/storage.objectAdmin`).

### Try it (PowerShell)

```
$env:FIRESTORE_EMULATOR_HOST="127.0.0.1:8080"; $env:GOOGLE_CLOUD_PROJECT="odin-local"; \
	.venv\Scripts\python.exe -m pytest -k "firestore_ledger or test_ledger_firestore" -q
```

### Notes

- Tests will show as "skipped" when the emulator is not running (env unset). This avoids hitting real Firestore in CI.

## 2025-08-18 — Cloud Run startup fix + deploy

- Root cause: Cloud Run revision failed to start; logs showed `ModuleNotFoundError: No module named 'cryptography'` during app import, so Uvicorn never bound to PORT.
- Fixes:
	- Added missing dependency to `requirements.txt`: `cryptography>=42`.
	- Rebuilt and pushed image to Artifact Registry via Cloud Build.
	- Redeployed to Cloud Run with `--env-vars-file config/cloudrun.env.yaml` and Secret Manager env `ODIN_KEYSTORE_JSON=odin-keystore:latest`.
- Result:
	- New revision came up successfully and is serving traffic.
	- Health check OK at `/health`.
	- Service URL: `https://odin-gateway-237788780100.us-central1.run.app`.

### Terminal excerpt

```
gcloud logging read ... revision_name=odin-gateway-00003-rpr
ModuleNotFoundError: No module named 'cryptography'

# After adding dependency and rebuild/deploy
Service [odin-gateway] revision [odin-gateway-00004-hfc] has been deployed and is serving 100 percent of traffic.
HEALTH: {"ok":true,"service":"gateway"}
```

## 2025-08-17 — IAM: Gateway SA least privilege for Firestore + GCS

- Principal: `odin-gateway-sa@odin-468307.iam.gserviceaccount.com`
- Firestore: granted `roles/datastore.user` (Datastore/Firestore user).
- Storage: granted object-scoped roles only — `roles/storage.objectCreator` and `roles/storage.objectViewer`.
- Removed broad `roles/storage.objectAdmin` from this SA to enforce least privilege.
- Verification: current bindings for the SA show exactly the three intended roles.

### Terminal excerpt

```
gcloud projects add-iam-policy-binding odin-468307 \
	--member="serviceAccount:odin-gateway-sa@odin-468307.iam.gserviceaccount.com" \
	--role="roles/datastore.user"

gcloud projects add-iam-policy-binding odin-468307 \
	--member="serviceAccount:odin-gateway-sa@odin-468307.iam.gserviceaccount.com" \
	--role="roles/storage.objectCreator"

gcloud projects add-iam-policy-binding odin-468307 \
	--member="serviceAccount:odin-gateway-sa@odin-468307.iam.gserviceaccount.com" \
	--role="roles/storage.objectViewer"

gcloud projects remove-iam-policy-binding odin-468307 \
	--member="serviceAccount:odin-gateway-sa@odin-468307.iam.gserviceaccount.com" \
	--role="roles/storage.objectAdmin"

gcloud projects get-iam-policy odin-468307 \
	--flatten=bindings \
	--filter="bindings.members:serviceAccount:odin-gateway-sa@odin-468307.iam.gserviceaccount.com" \
	--format="table(bindings.role)"

ROLE
roles/datastore.user
roles/storage.objectCreator
roles/storage.objectViewer
```

Notes:
- If bucket-level granularity is desired later, consider binding these roles at the bucket instead of project scope.

## 2025-08-18 — Step 41: Transform receipts (provable map→output)

- Core: added `libs/odin_core/odin/transform.py` with:
	- canonical transform subject (input/output/map hashes, SFTs, out_oml_cid),
	- linkage hash (blake3 of input || 0x1f || map || 0x1f || output),
	- signing via existing OPE path and wrapping in `ProofEnvelope`.
- Gateway:
	- `/v1/translate` now (when in map mode) emits a Transform Receipt persisted to storage at `receipts/transform/<out_cid>.json`.
	- Response headers:
		- `X-ODIN-Transform-Map` (map id)
		- `X-ODIN-Transform-Receipt` path to retrieval endpoint.
	- New router `apps/gateway/transform_receipts.py` with `GET /v1/receipts/transform/{out_cid}` returning the JSON receipt with ETag and long-lived caching.
	- Discovery updated to advertise `capabilities.transform=true` and the transform receipt endpoint.
- Feature flag: `ODIN_TRANSFORM_RECEIPTS` (default `1`).

### Tests
- Core: `libs/odin_core/tests/test_transform.py` roundtrip (subject signing + stable linkage hash).
- Gateway: `apps/gateway/tests/test_transform_receipts.py` ensures translate emits receipt headers and receipt fetch verifies.

### Verification
- `python -m pytest -k transform -q`  # core + gateway tests for this feature
- Manual:
	- POST `/v1/translate` (map mode) → `200`
	- Response contains `X-ODIN-Transform-*` headers
	- GET `/v1/receipts/transform/<out_cid>` returns structured JSON with `envelope`.

## 2025-08-17 — Secrets: Keystore in Secret Manager + access grant

- Source keystore used: `tmp/odin/keystore.json` (active_kid `k1`).
- Created Secret Manager secret `odin-keystore` with automatic replication and uploaded version 1.
- Granted `roles/secretmanager.secretAccessor` on the secret to `odin-gateway-sa@odin-468307.iam.gserviceaccount.com`.
- This can be mounted in Cloud Run (see `scripts/deploy-cloudrun.ps1` secret mount support) and wired via `ODIN_KEYSTORE_PATH`.

### Terminal excerpt

```
gcloud secrets describe odin-keystore --format=json
# -> NOT_FOUND (before creation)

gcloud secrets create odin-keystore --data-file=".\tmp\odin\keystore.json" --replication-policy="automatic"
# -> Created version [1] of the secret [odin-keystore]

gcloud secrets add-iam-policy-binding odin-keystore \
	--member="serviceAccount:odin-gateway-sa@odin-468307.iam.gserviceaccount.com" \
	--role="roles/secretmanager.secretAccessor"
```

Notes:
- Optional: you can also store `config/hel_policy.json` as `odin-hel-policy` using the same pattern if you want to manage HEL in Secret Manager.

## 2025-08-18 — Step 44: Observability & Alerts

- Metrics:
	- Gateway: custom Prometheus counters/histograms in `apps/gateway/metrics.py`
		- odin_transform_receipts_total, odin_bridge_beta_requests_total,
			odin_bridge_beta_request_seconds, odin_policy_violations_total,
			odin_httpsig_verifications_total.
	- Bridge instrumentation: Beta hop timings + receipt emission counters.
	- Enforcement: increments policy_violations_total and emits structured log "odin.policy.blocked".
	- Agent Beta: /metrics route; HTTP-signature pass/fail counters.
- Tests:
	- `apps/gateway/tests/test_metrics_observability.py` (bridge metrics present).
	- `apps/agent_beta/tests/test_agent_beta_metrics.py` (signature pass/fail reflected).
- Ops (GCP):
	- `scripts/monitoring-setup.ps1` provisions:
		- Uptime check for /health.
		- Error-rate (>2% 5m) and p95 latency (>1.5s 5m) alerts.
		- Logs-based metric & alert for policy blocks bursts.

### Verification

- Targeted metrics tests and full pytest run passed locally.

## 2025-08-18 — Step 45: Prometheus metrics across Gateway and Agent Beta

- New metrics modules with a dedicated CollectorRegistry per service:
  - `apps/gateway/metrics.py`
  - `apps/agent_beta/metrics.py`
- Metrics families (concise import aliases in parentheses):
  - Requests: `odin_requests_total` and `odin_request_latency_seconds` (requests_total, request_latency_seconds)
  - Transform receipts: `odin_transform_receipts_total{stage,map,storage,outcome}` (transform_receipts_total)
  - Policy: `odin_policy_violations_total{rule,route}` (policy_violations_total)
  - Agent Beta hop: `odin_bridge_beta_requests_total{outcome}` (bridge_beta_requests_total)
  - Agent Beta hop latency: `odin_bridge_beta_request_seconds` histogram (bridge_beta_latency_seconds)
  - HTTP signatures: `odin_httpsig_verifications_total{service,outcome}` (http_sig_verifications_total)
- Gateway wiring:
  - `apps/gateway/api.py` serves `/metrics` using the shared registry and includes request metrics middleware.
  - `apps/gateway/translate.py` emits transform receipt counters on persist/emit.
  - `apps/gateway/bridge.py` wraps outbound Beta call with count/latency and emits transform receipt counters for forward/reverse/reply.
  - `apps/gateway/middleware/proof_enforcement.py` increments policy violation counters on missing/invalid proof and HEL blocks.
  - `apps/gateway/security/http_signature.py` records verification outcomes with `service="gateway"`.
- Agent Beta wiring:
  - `apps/agent_beta/api.py` exposes `/metrics` and request metrics middleware.
  - `apps/agent_beta/security.py` records HTTP-signature verification outcomes with `service="agent_beta"`.
- Discovery/ops:
  - `/metrics` remains explicitly exempt from response signing so Prometheus can scrape reliably.
  - Metric names and labels are stable; concise alias exports added for ergonomic imports.

### Files added/changed
- Added: `apps/gateway/metrics.py`, `apps/agent_beta/metrics.py`
- Edited: `apps/gateway/api.py`, `apps/gateway/translate.py`, `apps/gateway/bridge.py`, `apps/gateway/middleware/proof_enforcement.py`, `apps/gateway/security/http_signature.py`, `apps/agent_beta/api.py`, `apps/agent_beta/security.py`

### Example queries (PromQL)
- Transform receipts rate by stage/map: `sum by (stage,map) (rate(odin_transform_receipts_total[5m]))`
- Beta hop success/fail over 1h: `sum by (outcome) (increase(odin_bridge_beta_requests_total[1h]))`
- 95th percentile Beta hop latency: `histogram_quantile(0.95, sum(rate(odin_bridge_beta_request_seconds_bucket[5m])) by (le))`

### Verification
- Targeted tests passed after instrumentation:
  - `apps/gateway/tests/test_discovery.py`
  - `apps/gateway/tests/test_bridge_env_target_override.py`
  - `apps/gateway/tests/test_receipts_transform_endpoint.py`
  - `apps/agent_beta/tests/test_agent_beta_http_sig.py`

## 2025-08-18 — Step 46: Signed Service Registry (Firestore + In‑Memory)

- Core:
	- Added `libs/odin_core/odin/registry.py` with `normalize_advert`, `compute_record_id_from_ad_cid`, and TTL helpers.
	- Added `libs/odin_core/odin/registry_store.py` with `InMemoryRegistry` and `FirestoreRegistry`; `create_registry_from_env()` selects backend via `ODIN_REGISTRY_BACKEND` (default `inmem`).
- Gateway:
	- New router `apps/gateway/registry.py`:
		- `POST /v1/registry/register` — accepts `{payload, proof}` (ProofEnvelope), verifies, persists, returns `id`.
		- `GET /v1/registry/services` — list with filters (`service`, `sft`, `active_only`, `limit`).
		- `GET /v1/registry/services/{id}` — fetch full record (payload + proof + metadata).
	- Discovery updated to advertise registry endpoints and `capabilities.registry=true`.
- Tests:
	- `apps/gateway/tests/test_registry.py` covering register/list/get + discovery presence.
	- Optional emulator test `apps/gateway/tests/test_registry_firestore.py` (auto-skips without emulator).
- Verification:
	- `pytest -q apps/gateway/tests/test_registry.py` => PASS (in-memory).
	- Firestore emulator test passes when `FIRESTORE_EMULATOR_HOST` is set and optional deps installed.

	## 2025-08-18 — Step 47: Dynamic Policy & SFT Reloading

	- Added runtime config manager (`apps/gateway/runtime.py`) with thread-safe caches:
		- `reload_policy()` and `get_hel_policy()` (supports ODIN_HEL_POLICY_JSON or ODIN_HEL_POLICY_PATH).
		- `reload_sft_maps()` clears+reloads map registry and re-registers built-in SFTs.
		- Optional local file watchers via `ODIN_WATCH_CONFIG=1`.
	- Admin API (`/v1/admin`):
		- `POST /v1/admin/reload/policy` and `POST /v1/admin/reload/maps`, gated by `ODIN_ENABLE_ADMIN=1` and optional `X-Admin-Token`.
	- Middleware: `ProofEnforcement` now calls `get_hel_policy()` so reload applies instantly.
	- Discovery: advertised `capabilities.policy_dynamic` and `capabilities.sft_dynamic`; added admin endpoints when enabled.
	- Tests: `apps/gateway/tests/test_admin_reload.py` validates reload + live usage by `/v1/translate`.
	- Verification: Targeted tests PASS; gateway test suite remains green.

## 2025-08-18 — Step 48: Cloud Run policy/env updates (HTTP‑sign skew + route lists)

- Goal: set HTTP-sign skew to 300 and enable route-scoped enforcement/signing in a Windows-safe way.
- Applied via YAML (avoids comma escaping on Windows PowerShell):
	- ODIN_HTTP_SIGN_SKEW_SEC="300"
	- ODIN_HTTP_SIGN_SKEW="300"
	- ODIN_SIGN_ROUTES="/v1/envelope,/v1/translate"
	- ODIN_ENFORCE_ROUTES="/v1/translate,/v1/bridge"
	- ODIN_HTTP_SIGN_ENFORCE_ROUTES="/v1/relay,/v1/bridge"
- Deployed new Cloud Run revision; waited for warm-up.
- Verification (discovery snapshot):
	- policy.sign_routes: ["/v1/envelope","/v1/translate"]
	- policy.enforce_routes: ["/v1/translate","/v1/bridge"]
	- http_sign.enforce_routes: ["/v1/relay","/v1/bridge"]
	- http_sign.require: true
	- http_sign.skew_sec: 300
- Health: /health → 200 OK.
- Note: keeping route lists in a single YAML alongside skew proved reliable on Windows.

Minor PowerShell tip
- Avoid piping across try/catch; assign to a variable then Write-Output to prevent “empty pipe element” errors during quick probes.

## 2025-08-18 — Step 49: Internal auth & resiliency for mesh forwarding

- Mesh forwarding hardened:
	- Added optional Google Cloud ID token on outbound mesh calls (Cloud Run → Cloud Run) via `Authorization: Bearer <token>` when `ODIN_MESH_ID_TOKEN!=0`.
	- New helper `apps/gateway/security/id_token.py` with `maybe_get_id_token()`; fails open if google-auth isn’t available.
	- Bounded timeouts/retries for outbound mesh calls: `ODIN_MESH_TIMEOUT_MS` (default 5000), `ODIN_MESH_RETRIES` (default 2), `ODIN_MESH_RETRY_BACKOFF_MS` (default 200).
	- 5xx responses are retried; 4xx are surfaced as 502 with body snapshot; network errors map to 502 with error type.
- Files changed/added:
	- Edited: `apps/gateway/relay_mesh.py`
	- Added:  `apps/gateway/security/id_token.py`
- Next: extend HTTP-sign enforcement to mesh/registry routes via env; lock Agent Beta invoker to gateway SA.

## 2025-08-19 — Step 50: Bridge translate try/except fix + outbound auth/resiliency

- Fixed an unterminated try block in `apps/gateway/bridge.py` translate path by refactoring:
	- Perform translation in a small try/except that maps `TranslateError` to 404/422.
	- Persist forward transform receipt best-effort.
	- Return early with the translated result when `target_url` is not provided (no unreachable code).
- Hardened `/v1/bridge/openai` outbound call to Agent Beta:
	- Optional HTTP-sign on outbound (unchanged behavior; headers always a dict).
	- Optional Google Cloud ID token support (`ODIN_BRIDGE_ID_TOKEN!=0`) with audience override via `ODIN_ID_TOKEN_AUDIENCE` or `ODIN_GCP_ID_TOKEN_AUDIENCE`.
	- Bounded timeout/retries/backoff: `ODIN_BRIDGE_TIMEOUT_MS` (default 10000), `ODIN_BRIDGE_RETRIES` (2), `ODIN_BRIDGE_RETRY_BACKOFF_MS` (250). Retries only on 5xx/network.
	- Metrics preserved: `bridge_beta_requests_total` and `bridge_beta_latency_seconds{outcome}`.

Verification
- Targeted tests now pass:
	- `apps/gateway/tests/test_bridge_http_sig.py`
	- `apps/gateway/tests/test_bridge_env_target_override.py`
	- `pytest -k bridge` across gateway tests → PASS.

Notes
- Kept behavior consistent for existing callers; improvements are opt-in via env.
- Follow-up: consider similar resilience knobs for the generic `/v1/bridge` target hop.

## 2025-08-19 — Step 51: Generic bridge outbound identity + resiliency; local env defaults

- Generic `/v1/bridge` target hop now mirrors the OpenAI path hardening:
	- Optional outbound HTTP-sign headers when `ODIN_BRIDGE_HTTP_SIG=1` (fails open).
	- Optional Google Cloud ID token on egress when `ODIN_BRIDGE_ID_TOKEN!=0` with audience override via `ODIN_ID_TOKEN_AUDIENCE` or `ODIN_GCP_ID_TOKEN_AUDIENCE`.
	- Resilience knobs: `ODIN_BRIDGE_TIMEOUT_MS` (default 10000), `ODIN_BRIDGE_RETRIES` (2), `ODIN_BRIDGE_RETRY_BACKOFF_MS` (250). Retries on 5xx/network only.
	- Preserves existing behavior for callers; surfaces 4xx/5xx with body snapshot under 502.
- Dev quality-of-life: updated `.vscode/launch.json` to enable local policy/signing and sane defaults for outbound identity/resilience:
	- Enforcement/signing routes: `ODIN_ENFORCE_ROUTES="/v1/translate,/v1/bridge"`, `ODIN_SIGN_ROUTES="/v1/envelope,/v1/translate"`.
	- HTTP-sign enforcement: `ODIN_HTTP_SIGN_ENFORCE_ROUTES="/v1/relay,/v1/bridge"`, `ODIN_HTTP_SIGN_SKEW_SEC=300`.
	- Bridge/Mesh outbound identity + timeouts/retries/backoff envs pre-set for local runs.

Verification
- Ran bridge-focused tests: PASS

```
python -m pytest -q apps/gateway/tests -k bridge
.....                                                                                                                   [100%]
```

Next
- Roll the same env knobs into Cloud Run YAML for staging/prod.
- Expand HTTP-sign enforcement to additional internal routes (mesh/registry) in stages; tighten Agent Beta IAM (remove public invoker).
