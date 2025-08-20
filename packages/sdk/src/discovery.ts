import type { FetchLike } from "./types";

export interface DiscoveryDoc {
  jwks_url: string;
  endpoints: Record<string, string>;
  policy?: { enforce_routes?: string[]; sign_routes?: string[]; sign_embed?: boolean };
  protocol?: { odin?: string; proof_version?: string };
  raw?: any;
}

export async function fetchDiscovery(baseUrl: string, fetchLike?: FetchLike): Promise<DiscoveryDoc> {
  const f = fetchLike ?? (globalThis as any).fetch;
  if (!f) throw new Error("fetchDiscovery: no fetch available");
  const url = baseUrl.replace(/\/+$/, "") + "/.well-known/odin/discovery.json";
  const res = await f(url);
  if (!res.ok) throw new Error(`fetchDiscovery: ${res.status}`);
  const j = await res.json();
  const jwks = j.jwks_url || (j.endpoints && j.endpoints.jwks);
  if (!jwks) throw new Error("fetchDiscovery: missing jwks_url");
  return {
    jwks_url: jwks,
    endpoints: j.endpoints || {},
    policy: j.policy,
    protocol: j.protocol,
    raw: j,
  };
}
