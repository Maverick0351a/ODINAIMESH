import { describe, it, expect } from "vitest";
import { fetchDiscovery, type DiscoveryDoc } from "../src/discovery";

function mockFetch(response: any, opts?: { status?: number }) {
  return async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const status = opts?.status ?? 200;
    const body = JSON.stringify(response);
    return new Response(body, { status, headers: { "content-type": "application/json" } });
  };
}

describe("fetchDiscovery", () => {
  it("parses jwks_url and endpoints", async () => {
    const doc = {
      jwks_url: "http://x/.well-known/odin/jwks.json",
      endpoints: { jwks: "/.well-known/odin/jwks.json", verify: "/v1/verify" },
      policy: { sign_embed: false },
      protocol: { odin: "0.1", proof_version: "1" },
    };
    const d = await fetchDiscovery("http://x", mockFetch(doc));
    expect(d.jwks_url.endsWith("/.well-known/odin/jwks.json")).toBe(true);
    expect(d.endpoints.verify).toBe("/v1/verify");
    expect(d.policy?.sign_embed).toBe(false);
    expect(d.protocol?.proof_version).toBe("1");
  });

  it("falls back to endpoints.jwks when jwks_url missing", async () => {
    const doc = { endpoints: { jwks: "/.well-known/odin/jwks.json" } };
    const d = await fetchDiscovery("http://x", mockFetch(doc));
    expect(d.jwks_url).toBe("/.well-known/odin/jwks.json");
  });

  it("throws on missing jwks_url", async () => {
    const doc = { endpoints: {} };
    await expect(fetchDiscovery("http://x", mockFetch(doc))).rejects.toThrow(/missing jwks_url/);
  });

  it("throws on non-OK HTTP", async () => {
    await expect(fetchDiscovery("http://x", mockFetch({}, { status: 404 }))).rejects.toThrow(/404/);
  });
});
