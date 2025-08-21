import { describe, it, expect } from "vitest";
import { fetchDiscovery } from "../src/discovery";

describe("fetchDiscovery", () => {
  it("parses jwks_url and endpoints", async () => {
    const fakeFetch = async (url: string) =>
      new Response(
        JSON.stringify({
          jwks_url: "http://gw/.well-known/odin/jwks.json",
          endpoints: { jwks: "/.well-known/odin/jwks.json", verify: "/v1/verify" },
          policy: { sign_embed: false },
          protocol: { odin: "0.1", proof_version: "1" },
        }),
        { status: 200, headers: { "content-type": "application/json" } }
      );

    const doc = await fetchDiscovery("http://gw", fakeFetch as any);
    expect(doc.jwks_url.endsWith("/.well-known/odin/jwks.json")).toBe(true);
    expect(doc.endpoints.verify).toBe("/v1/verify");
    expect(doc.policy?.sign_embed).toBe(false);
    expect(doc.protocol?.proof_version).toBe("1");
  });
});
