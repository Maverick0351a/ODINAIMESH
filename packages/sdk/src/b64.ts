import { base64url } from '@scure/base';

export function b64urlToBytes(s: string): Uint8Array {
  // Be forgiving: accept unpadded and translate URL alphabet -> standard base64
  let b64 = s.replace(/-/g, '+').replace(/_/g, '/');
  const pad = (4 - (b64.length % 4)) % 4;
  if (pad) b64 += '='.repeat(pad);
  // Use atob if available, else fall back to Buffer for Node
  if (typeof atob === 'function') {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  // Use global Buffer if available (Node ESM/CommonJS)
  const Buf: any = (globalThis as any).Buffer;
  if (!Buf || typeof Buf.from !== 'function') {
    throw new Error('base64 decode not supported in this environment');
  }
  const buf = Buf.from(b64, 'base64');
  return new Uint8Array(buf);
}

export function bytesToB64url(bytes: Uint8Array): string {
  return base64url.encode(bytes);
}
