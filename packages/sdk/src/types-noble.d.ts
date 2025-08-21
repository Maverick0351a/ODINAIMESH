declare module '@noble/hashes/blake3' {
  export function blake3(input: Uint8Array, opts?: { dkLen?: number }): Uint8Array;
}
