declare module '@scure/base' {
  export const base32: {
    encode(input: Uint8Array): string;
    decode(input: string): Uint8Array;
  };
  export const base64url: {
    encode(input: Uint8Array): string;
    decode(input: string): Uint8Array;
  };
}
