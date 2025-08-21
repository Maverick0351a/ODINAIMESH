import nacl from 'tweetnacl';
import { b64urlToBytes } from './b64';

export type OPE = {
  v: number;
  alg: 'Ed25519';
  ts_ns: number;
  kid: string;
  pub_b64u: string;
  content_hash_b3_256_b64u: string;
  sig_b64u: string;
  oml_cid?: string;
};

function concatBytes(...chunks: Uint8Array[]): Uint8Array {
  let total = 0;
  for (const c of chunks) total += c.length;
  const out = new Uint8Array(total);
  let offset = 0;
  for (const c of chunks) {
    out.set(c, offset);
    offset += c.length;
  }
  return out;
}

export function buildMessage(ts_ns: number, content: Uint8Array, oml_cid?: string): Uint8Array {
  const te = new TextEncoder();
  const prefix = te.encode('ODIN:OPE:v1');
  const pipe = te.encode('|');
  const ts = new Uint8Array(8);
  new DataView(ts.buffer).setBigUint64(0, BigInt(ts_ns), false);
  const base = concatBytes(prefix, pipe, ts, pipe, content);
  if (oml_cid) {
    return concatBytes(base, pipe, te.encode(oml_cid));
  }
  return base;
}

export function verifyOpe(ope: OPE, content: Uint8Array, expectedOmlCid?: string): boolean {
  if (expectedOmlCid !== undefined && ope.oml_cid !== expectedOmlCid) return false;
  const msg = buildMessage(ope.ts_ns, content, ope.oml_cid);
  const pub = b64urlToBytes(ope.pub_b64u);
  const sig = b64urlToBytes(ope.sig_b64u);
  return nacl.sign.detached.verify(msg, sig, pub);
}
