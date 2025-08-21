export type JWK = { kty: 'OKP'; crv: 'Ed25519'; x: string; kid?: string; alg?: string; use?: string };
export type JWKS = { keys: JWK[] };
import { b64urlToBytes } from './b64';

// Aliases matching alternative casing some callers prefer
export type Jwk = JWK;
export type Jwks = JWKS;

function looksLikeB64Url32Bytes(s: string): boolean {
  if (typeof s !== 'string' || !/^[A-Za-z0-9_-]+$/.test(s)) return false;
  try {
    const bytes = b64urlToBytes(s);
    return bytes.length === 32;
  } catch {
    return false;
  }
}

export function selectEd25519Key(jwks: JWKS, kid?: string): JWK | null {
  if (!jwks || !Array.isArray(jwks.keys) || jwks.keys.length === 0) return null;
  const targetKid = kid?.trim();
  const candidates = jwks.keys.filter(
    (k): k is JWK =>
      !!k &&
      k.kty === 'OKP' &&
      k.crv === 'Ed25519' &&
      typeof k.x === 'string'
  );
  if (candidates.length === 0) return null;
  if (targetKid) {
    const match = candidates.find(k => (k.kid ?? '').trim() === targetKid);
    return match ?? null;
  }
  const preferred = candidates.find(k => k.use === 'sig' || k.alg === 'EdDSA');
  return preferred ?? candidates[0] ?? null;
}

// Back-compat helper
export function findJwk(jwks: JWKS, kid: string): JWK | undefined {
  return selectEd25519Key(jwks, kid) ?? undefined;
}
