---
layout: home
title: ODIN Protocol
hero:
  name: ODIN Protocol
  text: An AI intranet — typed, signed, translated, auditable.
  tagline: Gateway + Relay + Realm Packs + Receipts + Bridge Pro
  image:
    src: /hero-diagram.png
    alt: ODIN Protocol Architecture
  actions:
    - theme: brand
      text: Start in 5 minutes
      link: "#quickstart"
    - theme: alt
      text: Install VS Code plugin
      link: /docs/sdk
features:
  - icon: 🔐
    title: Cryptographic Receipts
    details: Every hop writes a signed receipt; reconstruct chains by trace_id for complete audit trails.
  - icon: 🛡️
    title: HEL Governance
    details: Deny/allow/redact with hot reload and Prometheus metrics. Policy-as-code for AI safety.
  - icon: 🔄
    title: SFT Translation
    details: Deterministic maps with coverage, provenance, and validators. Optional LLM repair for edge cases.
  - icon: 🌉
    title: Bridge Guard / Engine
    details: Contract enforcement now; ISO 20022 transforms + approvals with Payments Bridge Pro add-on.
---

<div class="social-proof">
  <p class="social-proof-text">Designed for regulated environments</p>
  <div class="social-proof-badges">
    <span class="badge">SOC 2 Type II</span>
    <span class="badge">PCI DSS Level 1</span>
    <span class="badge">ISO 27001</span>
    <span class="badge">FIPS 140-2</span>
  </div>
</div>

## Quickstart {#quickstart}

> Deploy Gateway + Relay on Cloud Run, load a Realm Pack, run smoke tests.

### 1️⃣ Build & push containers

```powershell
# Set your project variables
$PROJECT='your-gcp-project'
$REGION='us-central1' 
$REPO='odin'
$TAG='v0.9.0'

# Build and push Gateway
gcloud builds submit --project $PROJECT --tag "$REGION-docker.pkg.dev/$PROJECT/$REPO/gateway:$TAG" .

# Build and push Relay  
gcloud builds submit --project $PROJECT --tag "$REGION-docker.pkg.dev/$PROJECT/$REPO/relay:$TAG" .
```

### 2️⃣ Create and upload Realm Packs

```powershell
# Business Realm Pack
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/odin-pack-setup.ps1 `
  -Realm business -Bucket your-realm-bucket -Version 0.9.0 -PackAsTgz

# Banking Realm Pack (for Bridge Pro)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/odin-pack-setup.ps1 `
  -Realm banking -Bucket your-realm-bucket -Version 0.9.0 -PackAsTgz
```

### 3️⃣ Deploy to Cloud Run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/deploy-cloudrun.ps1 `
  -Project $PROJECT -Region $REGION -Repo $REPO `
  -GatewayTag v0.9.0 -RelayTag v0.9.0 `
  -RealmPackUri "gs://your-realm-bucket/realms/business-0.9.0.tgz"
```

### 4️⃣ Run end-to-end smoke tests

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run-e2e.ps1 `
  -Region $REGION -Project $PROJECT
```

::: tip 🚀 Quick Deploy
Want to skip the setup? Use our **[one-click Cloud Run deploy button](https://console.cloud.google.com/cloudshell/editor?cloudshell_git_repo=https://github.com/Maverick0351a/ODINAIMESH)** to get started instantly.
:::

## How ODIN works

<div class="how-it-works">
  <div class="step">
    <div class="step-icon">🔍</div>
    <h3>Verify</h3>
    <p>Ed25519 OPE + Payload CID, JWKS rotation; deny spoofed calls with cryptographic proof.</p>
  </div>
  
  <div class="step">
    <div class="step-icon">⚖️</div>
    <h3>Govern</h3>
    <p>HEL rules for allow/deny/redact; dynamic reload without downtime, Prometheus metrics.</p>
  </div>
  
  <div class="step">
    <div class="step-icon">🔄</div>
    <h3>Translate</h3>
    <p>SFT maps with coverage, provenance, validators; optional LLM repair for complex transforms.</p>
  </div>
  
  <div class="step">
    <div class="step-icon">📋</div>
    <h3>Audit</h3>
    <p>Signed receipts, hop chain reconstruction, Prometheus metrics, compliance-ready trails.</p>
  </div>
</div>

::: info ✨ New in v0.9.0
**VAI** (agent registry), **SBOM** capture, **Merkle-Stream** receipts, **Roaming** passes for multi-tenant federation.
:::

## 🚀 Try ODIN Now

<OdinPlayground />

Experience secure AI-to-AI communication in your browser. Test with our demo models or bring your own API keys.

## Payments Bridge Pro (Add-on) {#bridge-pro}

<div class="bridge-pro-section">
  <div class="bridge-pro-content">
    <h3>🏦 Enterprise Payment Processing</h3>
    <p>Convert Business invoices to <strong>ISO 20022 pain.001</strong> with banking-grade validators, approval workflows, and cryptographic receipts.</p>
    
    <div class="bridge-pro-features">
      <ul>
        <li>✅ IBAN/BIC validation with checksum verification</li>
        <li>✅ ISO 4217 currency compliance</li>
        <li>✅ Approval workflows for high-value transactions</li>
        <li>✅ Cryptographic audit trails for SOX/PCI</li>
        <li>✅ Sub-200ms transformation latency</li>
        <li>✅ Usage-based billing integration</li>
      </ul>
    </div>

    <div class="bridge-pro-pricing">
      <p><strong>Base:</strong> $2,000/mo (10k messages included)</p>
      <p><strong>Usage:</strong> $0.50/execution beyond included</p>
    </div>

    <div class="bridge-pro-cta">
      <a href="/docs/bridges#payments-bridge-pro" class="cta-button">View Demo</a>
      <a href="https://calendly.com/odin-protocol/bridge-pro-demo" class="cta-button-secondary">Request Demo</a>
    </div>
  </div>
  
  <div class="bridge-pro-code">
    <h4>Invoice → ISO 20022 in 150ms</h4>
    
```json
// Input: Business Invoice
{
  "invoice_id": "INV-2024-001",
  "currency": "EUR",
  "total_amount": 50000.00,
  "from": {
    "name": "ACME Corp",
    "iban": "DE75512108001245126199"
  }
}

// Output: ISO 20022 pain.001
{
  "Document": {
    "CstmrCdtTrfInitn": {
      "GrpHdr": {
        "MsgId": "INV-2024-001",
        "NbOfTxs": "1",
        "CtrlSum": 50000.00
      }
    }
  }
}
```
  </div>
</div>

## Optional: Enable streaming

For **Merkle-Stream receipts** (real-time audit trails):

```bash
# Set environment variable in Relay
export ODIN_STREAM_ENABLED=1

# Use streaming endpoint and confirm Merkle root
curl -X POST /v1/mesh/stream \
  -H "X-ODIN-Stream-Root: expected"
```

<style>
.social-proof {
  text-align: center;
  padding: 2rem 0;
  border-bottom: 1px solid var(--vp-c-divider);
  margin-bottom: 3rem;
}

.social-proof-text {
  font-size: 0.9rem;
  color: var(--vp-c-text-2);
  margin-bottom: 1rem;
}

.social-proof-badges {
  display: flex;
  justify-content: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.badge {
  background: var(--vp-c-brand-soft);
  color: var(--vp-c-brand-dark);
  padding: 0.25rem 0.75rem;
  border-radius: 1rem;
  font-size: 0.8rem;
  font-weight: 600;
}

.how-it-works {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 2rem;
  margin: 3rem 0;
}

.step {
  text-align: center;
  padding: 2rem;
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  transition: transform 0.2s ease;
}

.step:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.step-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.step h3 {
  margin: 1rem 0 0.5rem 0;
  color: var(--vp-c-brand);
}

.bridge-pro-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 3rem;
  margin: 3rem 0;
  padding: 3rem;
  background: var(--vp-c-bg-soft);
  border-radius: 12px;
  border: 1px solid var(--vp-c-divider);
}

@media (max-width: 768px) {
  .bridge-pro-section {
    grid-template-columns: 1fr;
    gap: 2rem;
    padding: 2rem;
  }
}

.bridge-pro-features ul {
  margin: 1.5rem 0;
  padding: 0;
}

.bridge-pro-features li {
  margin: 0.5rem 0;
  font-size: 0.95rem;
}

.bridge-pro-pricing {
  background: var(--vp-c-brand-soft);
  padding: 1rem;
  border-radius: 8px;
  margin: 1.5rem 0;
}

.bridge-pro-pricing p {
  margin: 0.5rem 0;
  font-weight: 600;
}

.bridge-pro-cta {
  display: flex;
  gap: 1rem;
  margin-top: 2rem;
}

.cta-button {
  background: var(--vp-c-brand);
  color: white !important;
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  text-decoration: none !important;
  font-weight: 600;
  transition: background 0.2s ease;
}

.cta-button:hover {
  background: var(--vp-c-brand-dark);
}

.cta-button-secondary {
  background: transparent;
  color: var(--vp-c-brand) !important;
  padding: 0.75rem 1.5rem;
  border: 2px solid var(--vp-c-brand);
  border-radius: 8px;
  text-decoration: none !important;
  font-weight: 600;
  transition: all 0.2s ease;
}

.cta-button-secondary:hover {
  background: var(--vp-c-brand);
  color: white !important;
}

.bridge-pro-code {
  background: var(--vp-code-block-bg);
  padding: 1.5rem;
  border-radius: 8px;
  overflow-x: auto;
}

.bridge-pro-code h4 {
  margin-top: 0;
  margin-bottom: 1rem;
  color: var(--vp-c-brand);
}
</style>
