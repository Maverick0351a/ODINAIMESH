import { base32 } from "@scure/base";
import { blake3 } from "@noble/hashes/blake3";

// Compute ODIN CID: multihash(blake3-256) + multibase base32-lower with 'b' prefix
export function computeCid(bytes: Uint8Array): string {
  const digest = blake3(bytes, { dkLen: 32 });
  const mh = new Uint8Array(2 + digest.length);
  mh[0] = 0x1f; // blake3 code
  mh[1] = 32; // length
  mh.set(digest, 2);
  const b32 = base32.encode(mh).toLowerCase().replace(/=/g, "");
  return "b" + b32;
}
