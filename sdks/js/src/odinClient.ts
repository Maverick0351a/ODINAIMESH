export type Verification = { ok: boolean; omlCid?: string | null; hopId?: string | null; traceId?: string | null };

export class OdinClient {
  constructor(public baseUrl: string, public requireProof: boolean = true) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  static async fromDiscovery(url: string, opts?: { requireProof?: boolean }): Promise<OdinClient> {
    const base = url.replace(/\/$/, "");
    try {
      await fetch(`${base}/.well-known/odin/discovery.json`);
    } catch {}
    return new OdinClient(base, opts?.requireProof ?? true);
  }

  async postEnvelope(path: string, payload: any): Promise<{ data: any; verification: Verification }> {
    const resp = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    const verification: Verification = {
      ok: true,
      omlCid: resp.headers.get("x-odin-oml-cid"),
      hopId: resp.headers.get("x-odin-hop-id"),
      traceId: resp.headers.get("x-odin-trace-id"),
    };
    return { data, verification };
  }

  async postJson(path: string, body: any): Promise<any> {
    const resp = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  }
}
