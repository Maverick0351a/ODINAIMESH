# odin-protocol-sdk (Preview)

Preview SDK — API may change prior to 1.0. Use for evaluation only.

This SDK provides:
- OML/OML-C canonicalization and CID (BLAKE3-256 base32url) helpers
- JWKS verify helpers for ODIN Proof Envelopes (OPE)
- Simple HTTP client wrappers for ODIN Gateway

Install:
```bash
pip install odin-protocol-sdk
```

Quick start:
```python
from odin_protocol_sdk import OdinClient, compute_cid, verify_envelope

client = OdinClient.from_discovery("http://127.0.0.1:8080", require_proof=True)

payload = {"text": "hello"}
data, vr = client.post_envelope("/v1/envelope", payload)
print(vr.ok, vr.reason)

cid = compute_cid(payload)
print("cid:", cid)
```

License: Apache-2.0
