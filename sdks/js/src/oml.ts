import { blake3 } from "@noble/hashes/blake3";

export function canonicalJsonBytes(obj: any): Uint8Array {
  // Deterministic JSON: sorted keys, no whitespace, newline
  const json = JSON.stringify(obj, Object.keys(obj).sort(), 0);
  return new TextEncoder().encode(json + "\n");
}

export function computeCid(obj: any): string {
  const bytes = canonicalJsonBytes(obj);
  const hash = blake3(bytes);
  // base32 lower, no padding
  const b32 = base32(hash).toLowerCase().replace(/=+$/, "");
  return b32;
}

// Lightweight base32 (RFC 4648) encoder for small buffers
const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
function base32(bytes: Uint8Array): string {
  let out = "";
  let bits = 0;
  let value = 0;
  for (const b of bytes) {
    value = (value << 8) | b;
    bits += 8;
    while (bits >= 5) {
      out += ALPHABET[(value >>> (bits - 5)) & 31];
      bits -= 5;
    }
  }
  if (bits > 0) {
    out += ALPHABET[(value << (5 - bits)) & 31];
  }
  // pad to multiple of 8 characters
  while (out.length % 8 !== 0) out += "=";
  return out;
}
