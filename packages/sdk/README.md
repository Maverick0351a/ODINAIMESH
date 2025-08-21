# @odin-protocol/sdk

**ODIN Protocol — The Intranet for AI**  
JavaScript SDK for verifying Proof Envelopes and calling ODIN endpoints with hard-fail verification.

## Install

```bash
# from repo root (or cd packages/sdk)
npm install
npm run build
```

## API

- verifyEnvelope(envelope, { expectedCid?, jwks?, fetch? }) → Promise<Verification>
	- Recomputes CID from exact OML-C bytes, verifies Ed25519 signature (OPE JSON or signature-only), optionally resolves JWKS (inline/url or provided fetch).
	- Minimal HTTP client that POSTs JSON to endpoints returning `{ payload, proof }`. When `requireProof` (default true), it throws if proof is missing or invalid.
 fetchDiscovery(baseUrl, fetchLike?) → Promise<DiscoveryDoc>
 	- Fetches `/.well-known/odin/discovery.json` and returns `{ jwks_url, endpoints, protocol?, policy? }`.
 OdinClient(baseUrl, { fetch?, requireProof?, acceptProof? })
 	- Minimal HTTP client that POSTs JSON to endpoints returning `{ payload, proof }`. When `requireProof` (default true), it throws if proof is missing or invalid. Sets `X-ODIN-Accept-Proof` header to a default if not provided.
 OdinClient.fromDiscovery(baseUrl, { fetch?, requireProof?, acceptProof? }) → Promise<OdinClient>
 	- Bootstraps the client by reading discovery at the base URL. Accepts same options as the constructor.

## Notes

- In Node < 18, pass a `fetch` implementation to OdinClient and verifyEnvelope options.
- JWKS resolution precedence: options.jwks → envelope.jwks_inline → fetch(envelope.jwks_url).

## Discovery-based bootstrap

```ts
import { OdinClient } from "@odin-protocol/sdk";

// Auto-configure from gateway discovery; defaults X-ODIN-Accept-Proof to "embed,headers"
const client = await OdinClient.fromDiscovery("http://127.0.0.1:7070");

// Call an endpoint that returns a Proof Envelope; verification hard-fails on error
const { payload, verification } = await client.postEnvelope("/v1/echo", { hello: "world" });

// Override Accept-Proof per-call if needed
await client.postEnvelope("/v1/echo", { hi: "there" }, { "X-ODIN-Accept-Proof": "headers" });

// Or set a different default at construction
const headersOnly = new OdinClient("http://127.0.0.1:7070", { acceptProof: "headers" });
```

Behavioral notes:
- The client sets `X-ODIN-Accept-Proof` to `embed,headers` by default and only adds it if you didn’t provide the header yourself.
- Per-call headers take precedence; the client will not overwrite an explicitly provided `X-ODIN-Accept-Proof`.
