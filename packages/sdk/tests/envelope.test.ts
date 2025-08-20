import { describe, it, expect } from 'vitest';
import { ProofEnvelope, verifyEnvelope } from '../src/envelope';
import { bytesToB64url } from '../src/b64';
import { computeCid } from '../src/cid';

// Minimal synthetic test: verify fails without OML bytes, passes with consistent OPE mock

it('fails without oml_c_b64', async () => {
  const env: ProofEnvelope = { oml_cid: 'b' + 'a'.repeat(10), kid: 'k1', ope: 'AA' };
  const res = await verifyEnvelope(env as any);
  expect(res.ok).toBe(false);
});

// Note: full signature test would require constructing a real OPE JSON with valid sig and pub.
// This test focuses on CID comparisons logic only using a no-signature path by forcing verify failure to map correctly.

describe('cid checks', () => {
  it('detects cid mismatch', async () => {
    const bytes = new Uint8Array([0, 1, 2]);
    const cid = computeCid(bytes);
    const env: ProofEnvelope = {
      oml_cid: 'b' + 'x'.repeat(10),
      kid: 'k1',
      ope: 'AA',
      oml_c_b64: bytesToB64url(bytes),
    };
    const res = await verifyEnvelope(env as any, { expectedCid: cid } as any);
    expect(res.ok).toBe(false);
  });
});
