import nacl from 'tweetnacl';
import { OPE, verifyOpe } from './ope';
import { JWKS, selectEd25519Key } from './jwks';
import { computeCid } from './cid';
import { b64urlToBytes } from './b64';
import type { ProofEnvelope, Verification, FetchLike } from './types';

export function decodeOpeFromEnvelope(env: ProofEnvelope): OPE | null {
  try {
    const raw = b64urlToBytes(env.ope);
    const text = new TextDecoder().decode(raw);
    const obj = JSON.parse(text);
    if (obj && typeof obj === 'object' && obj.v && obj.alg && obj.ts_ns && obj.kid && obj.pub_b64u && obj.sig_b64u) {
      return obj as OPE;
    }
    return null;
  } catch {
    return null;
  }
}

function getGlobalFetch(): FetchLike | undefined {
  const f: any = (globalThis as any).fetch;
  return typeof f === 'function' ? (f as FetchLike) : undefined;
}

export async function verifyEnvelope(
  env: ProofEnvelope,
  opts?: { expectedCid?: string; jwks?: JWKS; fetch?: FetchLike }
): Promise<Verification> {
  const { expectedCid, jwks, fetch } = opts || {};

  // Load OML-C
  const oml = env.oml_c_b64 ? b64urlToBytes(env.oml_c_b64) : undefined;
  if (!oml) return { ok: false, cid: null, kid: env.kid ?? null, reason: 'missing_oml_c' };

  // Compute CID and compare with expected/claimed
  const cid = computeCid(oml);
  if (expectedCid && cid !== expectedCid) return { ok: false, cid, kid: env.kid ?? null, reason: 'cid_mismatch' };
  // Note: do not fail solely on env.oml_cid label mismatch; signature binds exact bytes.

  // Decode OPE. It may be either JSON-encoded OPE or raw 64-byte signature only in future; we support JSON today.
  const ope = decodeOpeFromEnvelope(env);
  if (ope) {
    // OPE JSON path
    const sigOk = verifyOpe(ope, oml, ope.oml_cid);
    if (!sigOk) return { ok: false, cid, kid: ope.kid ?? null, reason: 'verify_failed' };

    // Optional JWKS cross-check (kid/x)
    let jwksToUse: JWKS | undefined = jwks;
    if (!jwksToUse && env.jwks_inline && Array.isArray(env.jwks_inline.keys)) {
      jwksToUse = { keys: env.jwks_inline.keys as any } as JWKS;
    }
    if (!jwksToUse && env.jwks_url) {
      const f = fetch || getGlobalFetch();
      if (f) {
        try {
          const res = await f(env.jwks_url, { method: 'GET' });
          if (res.ok) {
            const data = await res.json();
            if (data && Array.isArray(data.keys)) jwksToUse = data as JWKS;
          }
        } catch {
          // ignore fetch errors; JWKS optional
        }
      }
    }
    if (jwksToUse) {
      const key = selectEd25519Key(jwksToUse, ope.kid);
      if (!key) return { ok: false, cid, kid: ope.kid ?? null, reason: 'kid_not_in_jwks' };
      if (key.x !== ope.pub_b64u) return { ok: false, cid, kid: ope.kid ?? null, reason: 'jwks_pub_mismatch' };
    }
    return { ok: true, cid, kid: ope.kid };
  }

  // Raw detached signature path: env.ope is the signature, JWKS is required to get pubkey by kid
  const sigBytes = b64urlToBytes(env.ope);
  if (sigBytes.length !== 64) return { ok: false, cid, kid: env.kid ?? null, reason: 'invalid_ope_format' };

  // Resolve JWKS via precedence: opts.jwks -> inline -> url
  let jwksToUse: JWKS | undefined = jwks;
  if (!jwksToUse && env.jwks_inline && Array.isArray(env.jwks_inline.keys)) {
    jwksToUse = { keys: env.jwks_inline.keys as any } as JWKS;
  }
  if (!jwksToUse && env.jwks_url) {
    const f = fetch || getGlobalFetch();
    if (f) {
      try {
        const res = await f(env.jwks_url, { method: 'GET' });
        if (res.ok) {
          const data = await res.json();
          if (data && Array.isArray(data.keys)) jwksToUse = data as JWKS;
        }
      } catch (e) {
        return { ok: false, cid, kid: env.kid ?? null, reason: 'jwks_fetch_failed' };
      }
    }
  }
  if (!jwksToUse) return { ok: false, cid, kid: env.kid ?? null, reason: 'no_jwks' };
  const key = selectEd25519Key(jwksToUse, env.kid);
  if (!key) return { ok: false, cid, kid: env.kid ?? null, reason: 'kid_not_in_jwks' };
  const pub = b64urlToBytes(key.x);
  if (pub.length !== 32) return { ok: false, cid, kid: env.kid ?? null, reason: 'invalid_jwk_x' };
  const ok = nacl.sign.detached.verify(oml, sigBytes, pub);
  return ok ? { ok: true, cid, kid: env.kid } : { ok: false, cid, kid: env.kid, reason: 'signature_invalid' };
}
