export type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export type ProofEnvelope = {
  oml_cid: string;
  kid: string;
  ope: string;          // base64url Ed25519 signature (64 bytes) OR base64url-encoded OPE JSON
  jwks_url?: string;
  jwks_inline?: { keys: Array<{ kty: 'OKP'; crv: 'Ed25519'; x: string; kid?: string; alg?: string; use?: string }> };
  oml_c_b64?: string;   // base64url OML-C canonical bytes
};

export type Verification = {
  ok: boolean;
  cid?: string | null;
  kid?: string | null;
  reason?: string | null;
};
