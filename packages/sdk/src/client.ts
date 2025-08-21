import type { FetchLike, ProofEnvelope, Verification } from "./types";
import { verifyEnvelope } from "./verify";
import { fetchDiscovery } from "./discovery";

const HDR_ACCEPT_PROOF = "X-ODIN-Accept-Proof";
const DEFAULT_ACCEPT_PROOF = "embed,headers";

/**
 * Minimal HTTP client that calls endpoints returning { payload, proof }.
 * If requireProof=true, throws on invalid/missing proofs.
 */
export class OdinClient {
  private base: string;
  private fetcher: FetchLike;
  private require: boolean;
  private acceptProof: string;

  constructor(baseUrl: string, opts?: { fetch?: FetchLike; requireProof?: boolean; acceptProof?: string }) {
    this.base = baseUrl.replace(/\/+$/, "") + "/";
    this.fetcher = opts?.fetch ?? (globalThis.fetch as FetchLike);
    if (typeof this.fetcher !== "function") {
      throw new Error("global fetch not available; supply opts.fetch or run Node >=18 / modern browser");
    }
    this.require = opts?.requireProof ?? true;
    this.acceptProof = opts?.acceptProof ?? DEFAULT_ACCEPT_PROOF;
  }

  static async fromDiscovery(baseUrl: string, opts?: { fetch?: FetchLike; requireProof?: boolean; acceptProof?: string }): Promise<OdinClient> {
    // Fetch discovery to validate the gateway and warm up any caches; use returned jwks_url implicitly at runtime.
    await fetchDiscovery(baseUrl, opts?.fetch);
    return new OdinClient(baseUrl, opts);
  }

  async postEnvelope<T = any>(route: string, body: any, headers?: Record<string, string>): Promise<{ payload: T; verification: Verification }> {
    const url = route.startsWith("http") ? route : new URL(route.replace(/^\//, ""), this.base).toString();
    const hdrs: Record<string, string> = { "content-type": "application/json", ...(headers || {}) };
    if (this.acceptProof && hdrs[HDR_ACCEPT_PROOF] == null) {
      hdrs[HDR_ACCEPT_PROOF] = this.acceptProof;
    }
    const res = await this.fetcher(url, {
      method: "POST",
      headers: hdrs,
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
    const data = await res.json();

    const proof: ProofEnvelope | undefined = data?.proof;
    if (!proof) {
      if (this.require) throw new Error("response missing 'proof' envelope");
      return { payload: (data?.payload ?? data) as T, verification: { ok: false, reason: "no proof" } as Verification };
    }

    const verification = await verifyEnvelope(proof, { fetch: this.fetcher });
    if (this.require && !verification.ok) {
      throw new Error(`ODIN proof verification failed: ${verification.reason ?? "unknown"}`);
    }
    const payload = (data && "payload" in data) ? (data.payload as T) : (data as T);
    return { payload, verification };
  }
}
