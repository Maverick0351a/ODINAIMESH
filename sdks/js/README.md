# odin-protocol-sdk (Preview)

Preview SDK — API may change prior to 1.0. Use for evaluation only.

Features:
- CID compute helpers (BLAKE3-256 over canonical JSON)
- JWKS verify helpers (Ed25519 keys)
- Lightweight HTTP client for ODIN Gateway

Install:
```bash
npm install odin-protocol-sdk
```

Quick start:
```ts
import { OdinClient, computeCid, verifyEnvelope } from "odin-protocol-sdk";

const client = await OdinClient.fromDiscovery("http://127.0.0.1:8080", { requireProof: true });

const payload = { text: "hello" };
const { data, verification } = await client.postEnvelope("/v1/envelope", payload);
console.log(verification.ok, verification.omlCid);

const cid = computeCid(payload);
console.log("cid:", cid);
```

License: Apache-2.0
