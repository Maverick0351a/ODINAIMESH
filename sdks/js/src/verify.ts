import * as ed from "@noble/ed25519";

export type VerifyResult = { ok: boolean; reason?: string; kid?: string };

function _atobStd(s: string): string {
  if (typeof atob === "function") return atob(s);
  // Node fallback
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  return Buffer.from(s, "base64").toString("binary");
}

function b64ToBytes(s: string): Uint8Array {
  const bin = _atobStd(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function b64uToBytes(s: string): Uint8Array {
  let t = s.replace(/-/g, "+").replace(/_/g, "/");
  const pad = (4 - (t.length % 4)) % 4;
  t += "=".repeat(pad);
  return b64ToBytes(t);
}

export async function verifyEnvelope(envelope: any, jwksUrl: string): Promise<VerifyResult> {
  try {
    const opeB64 = envelope?.ope;
    if (!opeB64) return { ok: false, reason: "missing_ope" };
  const ope = JSON.parse(new TextDecoder().decode(b64ToBytes(opeB64)));
    const kid = ope?.kid;
    if (!kid) return { ok: false, reason: "missing_kid" };
    const oml = envelope?.oml_c_b64;
    if (!oml) return { ok: false, reason: "missing_oml_c" };
  // oml_c_b64 is standard base64
  const content = b64ToBytes(oml);
    const sig = b64uToBytes(ope?.sig_b64u || "");

    const res = await fetch(jwksUrl);
    if (!res.ok) return { ok: false, reason: "jwks_fetch_failed" };
    const jwks = await res.json();
    const k = jwks?.keys?.find((k: any) => k.kid === kid && k.kty === "OKP" && k.crv === "Ed25519" && k.x);
    if (!k) return { ok: false, reason: "kid_not_found", kid };
    const pub = b64uToBytes(k.x);

    const ok = await ed.verify(sig, content, pub);
    return ok ? { ok: true } : { ok: false, reason: "verify_failed" };
  } catch (e: any) {
    return { ok: false, reason: `verify_failed:${e?.name || typeof e}` };
  }
}
