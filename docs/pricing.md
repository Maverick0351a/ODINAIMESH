# Pricing

## Developer (Free)

Perfect for getting started and small projects.

<div class="pricing-plan">
  <div class="plan-header">
    <h3>Free</h3>
    <div class="price">$0<span>/month</span></div>
  </div>
  
  <div class="plan-features">
    <ul>
      <li>✅ Click-to-deploy Cloud Run</li>
      <li>✅ Receipts & metrics</li>
      <li>✅ Community support</li>
      <li>✅ Basic Realm Packs</li>
      <li>✅ Up to 1,000 messages/month</li>
      <li>✅ GitHub integration</li>
    </ul>
  </div>
  
  <div class="plan-cta">
    <a href="/#quickstart" class="cta-button">Get Started</a>
  </div>
</div>

## Pro ($99/mo)

For teams that need higher limits and enterprise features.

<div class="pricing-plan featured">
  <div class="plan-header">
    <h3>Pro</h3>
    <div class="price">$99<span>/month</span></div>
    <div class="plan-badge">Most Popular</div>
  </div>
  
  <div class="plan-features">
    <ul>
      <li>✅ Everything in Free</li>
      <li>✅ Up to 100,000 messages/month</li>
      <li>✅ 99.9% SLA</li>
      <li>✅ Realm Packs hot-reload</li>
      <li>✅ Receipts export (JSON/CSV)</li>
      <li>✅ Priority email support</li>
      <li>✅ Advanced analytics dashboard</li>
      <li>✅ Custom SFT maps</li>
    </ul>
  </div>
  
  <div class="plan-cta">
    <a href="https://console.odin-protocol.dev/subscribe/pro" class="cta-button">Start Pro Trial</a>
  </div>
</div>

## Enterprise (Custom)

For large organizations with compliance and scale requirements.

<div class="pricing-plan">
  <div class="plan-header">
    <h3>Enterprise</h3>
    <div class="price">Custom<span>/pricing</span></div>
  </div>
  
  <div class="plan-features">
    <ul>
      <li>✅ Everything in Pro</li>
      <li>✅ Unlimited messages</li>
      <li>✅ SSO & private tenant</li>
      <li>✅ Custom SLOs & support</li>
      <li>✅ Compliance review (SOC 2, PCI)</li>
      <li>✅ Dedicated customer success</li>
      <li>✅ On-premise deployment option</li>
      <li>✅ Custom integrations</li>
    </ul>
  </div>
  
  <div class="plan-cta">
    <a href="https://calendly.com/odin-protocol/enterprise-demo" class="cta-button">Contact Sales</a>
  </div>
</div>

---

## Enterprise Add-ons

### Payments Bridge Pro

<div class="addon-section">
  <div class="addon-content">
    <h4>🏦 ISO 20022 Payment Processing</h4>
    <p>Convert business invoices to banking-standard ISO 20022 pain.001 messages with enterprise-grade validation, approval workflows, and cryptographic audit trails.</p>
    
    <div class="addon-features">
      <ul>
        <li>✅ IBAN/BIC validation with checksum verification</li>
        <li>✅ ISO 4217 currency compliance</li>
        <li>✅ High-value transaction approval workflows</li>
        <li>✅ Sub-200ms transformation latency</li>
        <li>✅ Cryptographic receipts for SOX/PCI compliance</li>
        <li>✅ Prometheus metrics & monitoring</li>
      </ul>
    </div>
  </div>
  
  <div class="addon-pricing">
    <div class="price-breakdown">
      <div class="price-item">
        <strong>Base:</strong> $2,000/month
        <span class="price-detail">Includes 10,000 messages</span>
      </div>
      <div class="price-item">
        <strong>Usage:</strong> $0.50/execution
        <span class="price-detail">Beyond included messages</span>
      </div>
    </div>
    
    <div class="addon-cta">
      <a href="/docs/bridges#payments-bridge-pro" class="cta-button">View Demo</a>
      <a href="https://calendly.com/odin-protocol/bridge-pro-demo" class="cta-button-secondary">Request Demo</a>
    </div>
  </div>
</div>

### Roaming Federation

<div class="addon-section">
  <div class="addon-content">
    <h4>🌐 Multi-Tenant AI Network</h4>
    <p>Enable secure AI-to-AI communication across organizational boundaries with cryptographic passes and audit trails.</p>
    
    <div class="addon-features">
      <ul>
        <li>✅ Cross-tenant message routing</li>
        <li>✅ Cryptographic pass validation</li>
        <li>✅ Audit trail preservation</li>
        <li>✅ Rate limiting & quotas</li>
      </ul>
    </div>
  </div>
  
  <div class="addon-pricing">
    <div class="price-breakdown">
      <div class="price-item">
        <strong>Usage:</strong> $0.005/pass
        <span class="price-detail">Pay only for what you use</span>
      </div>
    </div>
    
    <div class="addon-cta">
      <a href="/docs/roaming" class="cta-button">Learn More</a>
    </div>
  </div>
</div>

---

## Security & Compliance

All plans include enterprise-grade security:

<div class="security-features">
  <div class="security-item">
    <strong>🔐 WIF-only CI/CD</strong>
    <p>Workload Identity Federation for secure, keyless deployments</p>
  </div>
  
  <div class="security-item">
    <strong>🛡️ SSRF Guard</strong>
    <p>Server-side request forgery protection with allowlist validation</p>
  </div>
  
  <div class="security-item">
    <strong>🔑 JWKS Rotation</strong>
    <p>Automatic JSON Web Key Set rotation for cryptographic freshness</p>
  </div>
  
  <div class="security-item">
    <strong>👤 Admin-key Gating</strong>
    <p>Administrative operations require separate authentication</p>
  </div>
  
  <div class="security-item">
    <strong>📋 Receipt Audits</strong>
    <p>Cryptographic proof of every operation for compliance</p>
  </div>
  
  <div class="security-item">
    <strong>📊 Compliance Reports</strong>
    <p>SOC 2, PCI DSS, and custom compliance reporting</p>
  </div>
</div>

---

## Frequently Asked Questions

### How does billing work?

Messages are counted when they pass through the ODIN Gateway or Relay. Failed messages (validation errors, policy blocks) are not counted. Billing is calculated monthly with usage overages billed at the end of each cycle.

### What's included in support?

- **Free:** Community support via GitHub Issues and Discord
- **Pro:** Priority email support with 24-hour response SLA
- **Enterprise:** Dedicated customer success manager and phone support

### Can I deploy on-premise?

Enterprise customers can deploy ODIN on-premise or in their own cloud accounts. This includes full source code access and deployment automation.

### How do I migrate between plans?

You can upgrade or downgrade at any time. Changes take effect at the next billing cycle. Contact support for Enterprise migration assistance.

### What compliance certifications do you have?

ODIN Protocol maintains SOC 2 Type II, PCI DSS Level 1, and ISO 27001 certifications. Enterprise customers receive compliance documentation as part of their package.

---

<div class="bottom-cta">
  <h2>Ready to get started?</h2>
  <p>Deploy ODIN Protocol in minutes and start building secure AI-to-AI communication.</p>
  <div class="bottom-cta-buttons">
    <a href="/#quickstart" class="cta-button large">Start Free</a>
    <a href="https://calendly.com/odin-protocol/demo" class="cta-button-secondary large">Schedule Demo</a>
  </div>
</div>

<style>
.pricing-plan {
  border: 2px solid var(--vp-c-divider);
  border-radius: 12px;
  padding: 2rem;
  margin: 2rem 0;
  position: relative;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.pricing-plan:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.pricing-plan.featured {
  border-color: var(--vp-c-brand);
  background: var(--vp-c-brand-soft);
}

.plan-header {
  text-align: center;
  margin-bottom: 2rem;
}

.plan-header h3 {
  margin: 0 0 1rem 0;
  font-size: 1.5rem;
  color: var(--vp-c-brand);
}

.price {
  font-size: 3rem;
  font-weight: bold;
  color: var(--vp-c-text-1);
}

.price span {
  font-size: 1rem;
  color: var(--vp-c-text-2);
  font-weight: normal;
}

.plan-badge {
  background: var(--vp-c-brand);
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 20px;
  font-size: 0.9rem;
  font-weight: 600;
  margin-top: 1rem;
  display: inline-block;
}

.plan-features ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.plan-features li {
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--vp-c-divider-light);
}

.plan-features li:last-child {
  border-bottom: none;
}

.plan-cta {
  text-align: center;
  margin-top: 2rem;
}

.cta-button {
  background: var(--vp-c-brand);
  color: white !important;
  padding: 1rem 2rem;
  border-radius: 8px;
  text-decoration: none !important;
  font-weight: 600;
  transition: background 0.2s ease;
  display: inline-block;
}

.cta-button:hover {
  background: var(--vp-c-brand-dark);
}

.cta-button.large {
  padding: 1.25rem 2.5rem;
  font-size: 1.1rem;
}

.cta-button-secondary {
  background: transparent;
  color: var(--vp-c-brand) !important;
  padding: 1rem 2rem;
  border: 2px solid var(--vp-c-brand);
  border-radius: 8px;
  text-decoration: none !important;
  font-weight: 600;
  transition: all 0.2s ease;
  display: inline-block;
}

.cta-button-secondary:hover {
  background: var(--vp-c-brand);
  color: white !important;
}

.cta-button-secondary.large {
  padding: 1.25rem 2.5rem;
  font-size: 1.1rem;
}

.addon-section {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 2rem;
  margin: 2rem 0;
  padding: 2rem;
  background: var(--vp-c-bg-soft);
  border-radius: 12px;
  border: 1px solid var(--vp-c-divider);
}

@media (max-width: 768px) {
  .addon-section {
    grid-template-columns: 1fr;
    gap: 1.5rem;
  }
}

.addon-content h4 {
  margin-top: 0;
  color: var(--vp-c-brand);
}

.addon-features ul {
  list-style: none;
  padding: 0;
  margin: 1rem 0;
}

.addon-features li {
  margin: 0.5rem 0;
  font-size: 0.95rem;
}

.addon-pricing {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px solid var(--vp-c-divider);
}

.price-breakdown {
  margin-bottom: 1.5rem;
}

.price-item {
  margin: 1rem 0;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--vp-c-divider-light);
}

.price-item:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.price-detail {
  display: block;
  font-size: 0.9rem;
  color: var(--vp-c-text-2);
  margin-top: 0.25rem;
}

.addon-cta {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.addon-cta .cta-button,
.addon-cta .cta-button-secondary {
  text-align: center;
  padding: 0.75rem 1rem;
  font-size: 0.9rem;
}

.security-features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
  margin: 2rem 0;
}

.security-item {
  padding: 1.5rem;
  background: var(--vp-c-bg-soft);
  border-radius: 8px;
  border: 1px solid var(--vp-c-divider);
}

.security-item strong {
  color: var(--vp-c-brand);
  font-size: 1.1rem;
}

.security-item p {
  margin: 0.5rem 0 0 0;
  color: var(--vp-c-text-2);
}

.bottom-cta {
  text-align: center;
  padding: 3rem 2rem;
  background: var(--vp-c-brand-soft);
  border-radius: 12px;
  margin: 3rem 0;
}

.bottom-cta h2 {
  margin: 0 0 1rem 0;
  color: var(--vp-c-brand);
}

.bottom-cta p {
  margin: 0 0 2rem 0;
  color: var(--vp-c-text-2);
  font-size: 1.1rem;
}

.bottom-cta-buttons {
  display: flex;
  justify-content: center;
  gap: 1rem;
  flex-wrap: wrap;
}
</style>
