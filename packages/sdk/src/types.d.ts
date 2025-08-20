declare module 'tweetnacl' {
  namespace nacl {
    namespace sign {
      namespace detached {
        function verify(message: Uint8Array, signature: Uint8Array, publicKey: Uint8Array): boolean;
      }
    }
  }
  const nacl: {
    sign: {
      detached: {
        verify(message: Uint8Array, signature: Uint8Array, publicKey: Uint8Array): boolean;
      };
    };
  };
  export default nacl;
}
