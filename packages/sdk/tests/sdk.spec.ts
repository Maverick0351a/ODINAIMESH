import { describe, it, expect } from "vitest";
import nacl from "tweetnacl";
import { bytesToB64url } from "../src/b64";
import { verifyEnvelope } from "../src/verify";
import { OdinClient } from "../src/client";
import http from "node:http";

function startServer(handler: (req: http.IncomingMessage, res: http.ServerResponse) => void): Promise<{ url: string; close: () => Promise<void> }> {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(0, "127.0.0.1", () => {
      const addr = server.address() as any;
      const url = `http://${addr.address}:${addr.port}`;
      resolve({
        url,
        close: () =>
          new Promise<void>((r) => server.close(() => r())),
      });
    });
  });
}

describe("verifyEnvelope (inline JWKS)", () => {
  it("verifies a real signature end-to-end", async () => {
    const kp = nacl.sign.keyPair();
    const message = new TextEncoder().encode('{"x":1}');
    const sig = nacl.sign.detached(message, kp.secretKey);

    const jwks = { keys: [{ kty: "OKP", crv: "Ed25519", x: bytesToB64url(kp.publicKey), kid: "kid1", alg: "EdDSA", use: "sig" }] };

  const res = await verifyEnvelope({
      oml_cid: "testcid",
      kid: "kid1",
      ope: bytesToB64url(sig),
      jwks_inline: jwks as any,
      oml_c_b64: bytesToB64url(message),
    } as any);
    expect(res.ok).toBe(true);
    expect(res.kid).toBe("kid1");
  });
});

describe("OdinClient.postEnvelope", () => {
  it("posts and verifies using jwks_url", async () => {
    const kp = nacl.sign.keyPair();

    let jwksUrl = "";
    const server = await startServer((req, res) => {
      if (req.url === "/.well-known/odin/jwks.json") {
        const jwks = { keys: [{ kty: "OKP", crv: "Ed25519", x: bytesToB64url(kp.publicKey), kid: "kid1", alg: "EdDSA", use: "sig" }] };
        res.setHeader("content-type", "application/json");
        res.end(JSON.stringify(jwks));
        return;
      }
      if (req.method === "POST" && req.url === "/v1/envelope") {
        const chunks: Buffer[] = [];
        req.on("data", (c) => chunks.push(c));
        req.on("end", () => {
          const body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
          const msg = Buffer.from(JSON.stringify(body));
          const sig = nacl.sign.detached(new Uint8Array(msg), kp.secretKey);
          const proof = {
            oml_cid: "testcid",
            kid: "kid1",
            ope: bytesToB64url(sig),
            jwks_url: `${jwksUrl}/.well-known/odin/jwks.json`,
            oml_c_b64: bytesToB64url(new Uint8Array(msg)),
          };
          res.setHeader("content-type", "application/json");
          res.end(JSON.stringify({ payload: body, proof }));
        });
        return;
      }
      res.statusCode = 404;
      res.end("not found");
    });

    jwksUrl = server.url;

    try {
      const client = new OdinClient(server.url, { requireProof: true });
      try {
        const { payload, verification } = await client.postEnvelope(`${server.url}/v1/envelope`, { hello: "world" });
        expect(payload).toEqual({ hello: "world" });
        expect(verification.ok).toBe(true);
        expect(verification.kid).toBe("kid1");
      } catch (e: any) {
        throw e;
      }
    } finally {
      await server.close();
    }
  });

  it("fromDiscovery sets default Accept-Proof and allows override", async () => {
    const kp = nacl.sign.keyPair();

    let seenAccept: string | null = null;
    const server = await startServer((req, res) => {
    if (req.url === "/.well-known/odin/discovery.json") {
        const disc = {
      jwks_url: `${"http://127.0.0.1"}/.well-known/odin/jwks.json`,
          endpoints: { jwks: "/.well-known/odin/jwks.json", envelope: "/v1/envelope" },
        };
        res.setHeader("content-type", "application/json");
        res.end(JSON.stringify(disc));
        return;
      }
      if (req.url === "/.well-known/odin/jwks.json") {
        const jwks = { keys: [{ kty: "OKP", crv: "Ed25519", x: bytesToB64url(kp.publicKey), kid: "kid1", alg: "EdDSA", use: "sig" }] };
        res.setHeader("content-type", "application/json");
        res.end(JSON.stringify(jwks));
        return;
      }
      if (req.method === "POST" && req.url === "/v1/envelope") {
        seenAccept = req.headers["x-odin-accept-proof"] as string | null;
        const chunks: Buffer[] = [];
        req.on("data", (c) => chunks.push(c));
        req.on("end", () => {
          const body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
          const msg = Buffer.from(JSON.stringify(body));
          const sig = nacl.sign.detached(new Uint8Array(msg), kp.secretKey);
          const proof = {
            oml_cid: "testcid",
            kid: "kid1",
            ope: bytesToB64url(sig),
            jwks_url: `${server.url}/.well-known/odin/jwks.json`,
            oml_c_b64: bytesToB64url(new Uint8Array(msg)),
          };
          res.setHeader("content-type", "application/json");
          res.end(JSON.stringify({ payload: body, proof }));
        });
        return;
      }
      res.statusCode = 404;
      res.end("not found");
    });

    try {
      const client = await OdinClient.fromDiscovery(server.url);
      const r1 = await client.postEnvelope("/v1/envelope", { a: 1 });
      expect(r1.verification.ok).toBe(true);
      expect(seenAccept).toBe("embed,headers");

      // Caller override should be respected
      const r2 = await client.postEnvelope("/v1/envelope", { a: 2 }, { "X-ODIN-Accept-Proof": "headers" });
      expect(r2.verification.ok).toBe(true);
      expect(seenAccept).toBe("headers");
    } finally {
      await server.close();
    }
  });
});
