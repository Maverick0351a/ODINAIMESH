# Security & Compliance

ODIN Protocol is built with enterprise-grade security and compliance from the ground up. This document covers our security model, compliance certifications, and best practices for secure AI-to-AI communication.

## Security Architecture

### Zero-Trust Design

<div class="security-principle">
  <h4>🔒 Workload Identity Federation (WIF)</h4>
  <p>All deployments use WIF for keyless authentication, eliminating the need for service account keys in CI/CD pipelines.</p>
  
  <div class="implementation-details">
    <strong>Implementation:</strong>
    <ul>
      <li>GitHub Actions authenticate using OpenID Connect (OIDC)</li>
      <li>Google Cloud verifies tokens through OIDC provider</li>
      <li>No long-lived credentials stored in repositories</li>
      <li>Automatic token rotation and validation</li>
    </ul>
  </div>
</div>

<div class="security-principle">
  <h4>🛡️ SSRF Protection</h4>
  <p>Server-Side Request Forgery (SSRF) protection with allowlist validation prevents unauthorized internal network access.</p>
  
  <div class="implementation-details">
    <strong>Protection Mechanisms:</strong>
    <ul>
      <li>URL allowlist validation for all outbound requests</li>
      <li>Private IP range blocking (RFC 1918, RFC 4193)</li>
      <li>DNS resolution filtering</li>
      <li>Request timeout and size limits</li>
    </ul>
  </div>
</div>

<div class="security-principle">
  <h4>🔑 JWKS Rotation</h4>
  <p>Automatic JSON Web Key Set (JWKS) rotation ensures cryptographic freshness and limits blast radius of key compromise.</p>
  
  <div class="implementation-details">
    <strong>Key Management:</strong>
    <ul>
      <li>Automated key rotation every 24 hours</li>
      <li>Graceful transition with overlap periods</li>
      <li>Remote JWKS endpoint validation</li>
      <li>Algorithm agility (ES256, RS256 support)</li>
    </ul>
  </div>
</div>

<div class="security-principle">
  <h4>👤 Admin Key Gating</h4>
  <p>Administrative operations require separate authentication to prevent privilege escalation and ensure audit trails.</p>
  
  <div class="implementation-details">
    <strong>Admin Controls:</strong>
    <ul>
      <li>Separate admin API keys with limited scope</li>
      <li>Multi-factor authentication for admin operations</li>
      <li>Admin action logging and alerting</li>
      <li>Time-limited admin sessions</li>
    </ul>
  </div>
</div>

### Cryptographic Security

<div class="crypto-section">
  <h4>🔐 Message Encryption</h4>
  
  <div class="crypto-details">
    <div class="crypto-item">
      <strong>At Rest:</strong>
      <ul>
        <li>AES-256-GCM encryption for stored messages</li>
        <li>Envelope encryption with Cloud KMS</li>
        <li>Per-tenant encryption keys</li>
        <li>Automatic key rotation</li>
      </ul>
    </div>
    
    <div class="crypto-item">
      <strong>In Transit:</strong>
      <ul>
        <li>TLS 1.3 for all external connections</li>
        <li>mTLS for service-to-service communication</li>
        <li>Certificate pinning and validation</li>
        <li>Perfect Forward Secrecy (PFS)</li>
      </ul>
    </div>
    
    <div class="crypto-item">
      <strong>In Processing:</strong>
      <ul>
        <li>Memory encryption for sensitive data</li>
        <li>Secure enclaves for key operations</li>
        <li>Constant-time operations to prevent timing attacks</li>
        <li>Secure memory allocation and deallocation</li>
      </ul>
    </div>
  </div>
</div>

### Receipt System

ODIN's cryptographic receipt system provides tamper-evident proof of every operation:

```json
{
  "receipt_id": "rcpt_abc123def456",
  "message_id": "msg_789xyz012",
  "timestamp": "2024-01-15T14:30:00Z",
  "operation": "message.sent",
  "hash": "sha256:b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
  "signature": {
    "algorithm": "ES256",
    "keyid": "key_2024_001",
    "signature": "..."
  },
  "chain": {
    "previous": "rcpt_previous456",
    "merkle_root": "..."
  }
}
```

## Compliance Certifications

### SOC 2 Type II

<div class="compliance-cert">
  <div class="cert-badge">
    <strong>✅ SOC 2 Type II</strong>
    <span>Service Organization Control</span>
  </div>
  
  <div class="cert-details">
    <h5>Trust Service Criteria Coverage:</h5>
    <ul>
      <li><strong>Security:</strong> Protection against unauthorized access</li>
      <li><strong>Availability:</strong> 99.9% uptime commitment</li>
      <li><strong>Processing Integrity:</strong> Complete and accurate processing</li>
      <li><strong>Confidentiality:</strong> Information designated as confidential is protected</li>
      <li><strong>Privacy:</strong> Personal information collection, use, retention, and disposal</li>
    </ul>
    
    <p><strong>Audit Period:</strong> Annual audits by independent CPA firms</p>
    <p><strong>Report Access:</strong> Available to Enterprise customers under NDA</p>
  </div>
</div>

### PCI DSS Level 1

<div class="compliance-cert">
  <div class="cert-badge">
    <strong>✅ PCI DSS Level 1</strong>
    <span>Payment Card Industry Data Security Standard</span>
  </div>
  
  <div class="cert-details">
    <h5>Requirements Compliance:</h5>
    <ul>
      <li><strong>Network Security:</strong> Firewalls and secure network architecture</li>
      <li><strong>Data Protection:</strong> Cardholder data encryption and protection</li>
      <li><strong>Vulnerability Management:</strong> Regular security testing and updates</li>
      <li><strong>Access Control:</strong> Restrict access to cardholder data by business need</li>
      <li><strong>Monitoring:</strong> Regular monitoring and testing of networks</li>
      <li><strong>Information Security:</strong> Maintain information security policy</li>
    </ul>
    
    <p><strong>Validation:</strong> Quarterly ASV scans and annual on-site assessments</p>
    <p><strong>Scope:</strong> Bridge Pro payment processing components</p>
  </div>
</div>

### ISO 27001

<div class="compliance-cert">
  <div class="cert-badge">
    <strong>✅ ISO 27001</strong>
    <span>Information Security Management System</span>
  </div>
  
  <div class="cert-details">
    <h5>Control Objectives:</h5>
    <ul>
      <li><strong>A.5:</strong> Information security policies</li>
      <li><strong>A.6:</strong> Organization of information security</li>
      <li><strong>A.8:</strong> Asset management</li>
      <li><strong>A.10:</strong> Cryptography</li>
      <li><strong>A.12:</strong> Operations security</li>
      <li><strong>A.13:</strong> Communications security</li>
      <li><strong>A.14:</strong> System acquisition, development and maintenance</li>
      <li><strong>A.16:</strong> Information security incident management</li>
      <li><strong>A.17:</strong> Information security aspects of business continuity management</li>
      <li><strong>A.18:</strong> Compliance</li>
    </ul>
    
    <p><strong>Certification Body:</strong> Accredited third-party certification body</p>
    <p><strong>Surveillance:</strong> Annual surveillance audits</p>
  </div>
</div>

## Regional Compliance

### GDPR (European Union)

<div class="regional-compliance">
  <h4>🇪🇺 General Data Protection Regulation</h4>
  
  <div class="gdpr-controls">
    <div class="gdpr-item">
      <strong>Data Minimization:</strong>
      <p>ODIN processes only the minimum personal data necessary for operation</p>
    </div>
    
    <div class="gdpr-item">
      <strong>Right to Erasure:</strong>
      <p>Complete data deletion within 30 days of request</p>
    </div>
    
    <div class="gdpr-item">
      <strong>Data Portability:</strong>
      <p>Export data in machine-readable format (JSON/CSV)</p>
    </div>
    
    <div class="gdpr-item">
      <strong>Consent Management:</strong>
      <p>Granular consent controls with audit trails</p>
    </div>
    
    <div class="gdpr-item">
      <strong>Data Protection Officer:</strong>
      <p>Designated DPO for privacy inquiries: dpo@odin-protocol.dev</p>
    </div>
  </div>
</div>

### CCPA (California)

<div class="regional-compliance">
  <h4>🇺🇸 California Consumer Privacy Act</h4>
  
  <div class="ccpa-controls">
    <div class="ccpa-item">
      <strong>Right to Know:</strong>
      <p>Detailed disclosure of personal information collection and use</p>
    </div>
    
    <div class="ccpa-item">
      <strong>Right to Delete:</strong>
      <p>Consumer-initiated deletion with verification process</p>
    </div>
    
    <div class="ccpa-item">
      <strong>Right to Non-Discrimination:</strong>
      <p>No service degradation for exercising privacy rights</p>
    </div>
    
    <div class="ccpa-item">
      <strong>Sale Opt-Out:</strong>
      <p>ODIN does not sell personal information to third parties</p>
    </div>
  </div>
</div>

## Security Best Practices

### Deployment Security

<div class="best-practices-section">
  <h4>🚀 Secure Deployment</h4>
  
```yaml
# Cloud Run secure deployment
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  annotations:
    run.googleapis.com/execution-environment: gen2
    run.googleapis.com/cpu-throttling: "false"
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/vpc-access-connector: projects/PROJECT/locations/REGION/connectors/odin-connector
        run.googleapis.com/vpc-access-egress: private-ranges-only
    spec:
      containerConcurrency: 100
      timeoutSeconds: 300
      serviceAccountName: odin-gateway@PROJECT.iam.gserviceaccount.com
      containers:
      - image: gcr.io/PROJECT/odin-gateway:latest
        env:
        - name: ODIN_JWKS_URL
          valueFrom:
            secretKeyRef:
              name: odin-secrets
              key: jwks-url
        resources:
          limits:
            cpu: 2000m
            memory: 4Gi
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
          readOnlyRootFilesystem: true
```
</div>

### Network Security

<div class="best-practices-section">
  <h4>🌐 Network Configuration</h4>
  
```bash
# VPC configuration
gcloud compute networks create odin-vpc \
  --subnet-mode regional

# Private subnet for services
gcloud compute networks subnets create odin-subnet \
  --network odin-vpc \
  --range 10.0.0.0/24 \
  --region us-central1 \
  --enable-private-ip-google-access

# Cloud NAT for outbound connectivity
gcloud compute routers create odin-router \
  --network odin-vpc \
  --region us-central1

gcloud compute routers nats create odin-nat \
  --router odin-router \
  --region us-central1 \
  --nat-all-subnet-ip-ranges \
  --auto-allocate-nat-external-ips
```
</div>

### Authentication & Authorization

<div class="best-practices-section">
  <h4>🔐 Auth Configuration</h4>
  
```python
# Example secure client configuration
from odin_sdk import OdinClient
import os

client = OdinClient(
    gateway=os.getenv('ODIN_GATEWAY_URL'),
    api_key=os.getenv('ODIN_API_KEY'),
    
    # Security options
    verify_tls=True,
    timeout=30,
    retry_config={
        'max_retries': 3,
        'backoff_factor': 1.0,
        'status_forcelist': [500, 502, 503, 504]
    },
    
    # Authentication
    auth_method='bearer',
    jwks_url=os.getenv('ODIN_JWKS_URL'),
    token_refresh_threshold=300  # 5 minutes
)

# Validate connection
health = client.health_check()
assert health['status'] == 'healthy'
```
</div>

## Incident Response

### Security Incident Classification

<div class="incident-classification">
  <div class="severity-level critical">
    <h4>Critical (P0)</h4>
    <ul>
      <li>Data breach or unauthorized access</li>
      <li>Service unavailability > 1 hour</li>
      <li>Cryptographic key compromise</li>
    </ul>
    <strong>Response Time:</strong> 15 minutes
  </div>
  
  <div class="severity-level high">
    <h4>High (P1)</h4>
    <ul>
      <li>Security vulnerability exploitation</li>
      <li>Performance degradation > 50%</li>
      <li>Compliance violation</li>
    </ul>
    <strong>Response Time:</strong> 1 hour
  </div>
  
  <div class="severity-level medium">
    <h4>Medium (P2)</h4>
    <ul>
      <li>Minor security policy violation</li>
      <li>Non-critical feature unavailability</li>
      <li>Performance degradation < 50%</li>
    </ul>
    <strong>Response Time:</strong> 4 hours
  </div>
  
  <div class="severity-level low">
    <h4>Low (P3)</h4>
    <ul>
      <li>Documentation or cosmetic issues</li>
      <li>Enhancement requests</li>
      <li>Non-urgent maintenance</li>
    </ul>
    <strong>Response Time:</strong> Next business day
  </div>
</div>

### Incident Response Process

<div class="incident-process">
  <div class="process-step">
    <h4>1. Detection & Classification</h4>
    <ul>
      <li>Automated monitoring alerts</li>
      <li>Customer reports</li>
      <li>Security tool notifications</li>
      <li>Initial severity assessment</li>
    </ul>
  </div>
  
  <div class="process-step">
    <h4>2. Containment</h4>
    <ul>
      <li>Isolate affected systems</li>
      <li>Preserve evidence</li>
      <li>Notify stakeholders</li>
      <li>Activate incident response team</li>
    </ul>
  </div>
  
  <div class="process-step">
    <h4>3. Investigation</h4>
    <ul>
      <li>Root cause analysis</li>
      <li>Impact assessment</li>
      <li>Evidence collection</li>
      <li>Timeline reconstruction</li>
    </ul>
  </div>
  
  <div class="process-step">
    <h4>4. Recovery</h4>
    <ul>
      <li>System restoration</li>
      <li>Data recovery if needed</li>
      <li>Security patch deployment</li>
      <li>Service validation</li>
    </ul>
  </div>
  
  <div class="process-step">
    <h4>5. Post-Incident</h4>
    <ul>
      <li>Lessons learned documentation</li>
      <li>Process improvement</li>
      <li>Customer communication</li>
      <li>Regulatory notifications if required</li>
    </ul>
  </div>
</div>

## Security Contact

<div class="security-contact">
  <h4>🚨 Report Security Issues</h4>
  
  <div class="contact-methods">
    <div class="contact-method">
      <strong>Email:</strong>
      <a href="mailto:security@odin-protocol.dev">security@odin-protocol.dev</a>
      <p>PGP Key: <a href="https://odin-protocol.dev/security.pgp">Download</a></p>
    </div>
    
    <div class="contact-method">
      <strong>Bug Bounty:</strong>
      <a href="https://hackerone.com/odin-protocol">HackerOne</a>
      <p>Rewards up to $10,000 for critical vulnerabilities</p>
    </div>
    
    <div class="contact-method">
      <strong>Emergency:</strong>
      <a href="tel:+1-555-ODIN-SEC">+1-555-ODIN-SEC</a>
      <p>24/7 security hotline for critical issues</p>
    </div>
  </div>
  
  <div class="response-commitment">
    <h5>Response Commitment:</h5>
    <ul>
      <li><strong>Critical:</strong> 2 hours</li>
      <li><strong>High:</strong> 24 hours</li>
      <li><strong>Medium:</strong> 72 hours</li>
      <li><strong>Low:</strong> 1 week</li>
    </ul>
  </div>
</div>

<style>
.security-principle {
  margin: 2rem 0;
  padding: 2rem;
  background: var(--vp-c-bg-soft);
  border-radius: 12px;
  border-left: 4px solid var(--vp-c-brand);
}

.security-principle h4 {
  margin: 0 0 1rem 0;
  color: var(--vp-c-brand);
}

.implementation-details {
  margin: 1.5rem 0;
  padding: 1rem;
  background: var(--vp-c-bg);
  border-radius: 8px;
  border: 1px solid var(--vp-c-divider);
}

.implementation-details strong {
  color: var(--vp-c-text-1);
  display: block;
  margin-bottom: 0.5rem;
}

.implementation-details ul {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}

.crypto-section {
  margin: 2rem 0;
  padding: 2rem;
  background: var(--vp-c-bg-soft);
  border-radius: 12px;
  border: 1px solid var(--vp-c-divider);
}

.crypto-section h4 {
  margin: 0 0 1.5rem 0;
  color: var(--vp-c-brand);
}

.crypto-details {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
}

.crypto-item {
  padding: 1.5rem;
  background: var(--vp-c-bg);
  border-radius: 8px;
  border: 1px solid var(--vp-c-divider);
}

.crypto-item strong {
  color: var(--vp-c-brand);
  font-size: 1.1rem;
  display: block;
  margin-bottom: 1rem;
}

.crypto-item ul {
  margin: 0;
  padding-left: 1.5rem;
}

.crypto-item li {
  margin: 0.5rem 0;
}

.compliance-cert {
  margin: 2rem 0;
  padding: 2rem;
  background: var(--vp-c-bg-soft);
  border-radius: 12px;
  border: 1px solid var(--vp-c-divider);
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 2rem;
  align-items: start;
}

@media (max-width: 768px) {
  .compliance-cert {
    grid-template-columns: 1fr;
    gap: 1rem;
  }
}

.cert-badge {
  padding: 1.5rem;
  background: var(--vp-c-brand);
  color: white;
  border-radius: 8px;
  text-align: center;
  min-width: 200px;
}

.cert-badge strong {
  display: block;
  font-size: 1.2rem;
  margin-bottom: 0.5rem;
}

.cert-badge span {
  font-size: 0.9rem;
  opacity: 0.9;
}

.cert-details h5 {
  margin: 0 0 1rem 0;
  color: var(--vp-c-brand);
}

.cert-details ul {
  margin: 1rem 0;
  padding-left: 1.5rem;
}

.cert-details li {
  margin: 0.5rem 0;
}

.cert-details li strong {
  color: var(--vp-c-text-1);
}

.cert-details p {
  margin: 1rem 0;
  color: var(--vp-c-text-2);
}

.cert-details p strong {
  color: var(--vp-c-brand);
}

.regional-compliance {
  margin: 2rem 0;
  padding: 2rem;
  background: var(--vp-c-bg-soft);
  border-radius: 12px;
  border: 1px solid var(--vp-c-divider);
}

.regional-compliance h4 {
  margin: 0 0 1.5rem 0;
  color: var(--vp-c-brand);
}

.gdpr-controls,
.ccpa-controls {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1rem;
}

.gdpr-item,
.ccpa-item {
  padding: 1rem;
  background: var(--vp-c-bg);
  border-radius: 8px;
  border: 1px solid var(--vp-c-divider);
}

.gdpr-item strong,
.ccpa-item strong {
  color: var(--vp-c-brand);
  display: block;
  margin-bottom: 0.5rem;
}

.gdpr-item p,
.ccpa-item p {
  margin: 0;
  color: var(--vp-c-text-2);
  font-size: 0.95rem;
}

.best-practices-section {
  margin: 2rem 0;
  padding: 2rem;
  background: var(--vp-c-bg-soft);
  border-radius: 12px;
  border: 1px solid var(--vp-c-divider);
}

.best-practices-section h4 {
  margin: 0 0 1.5rem 0;
  color: var(--vp-c-brand);
}

.incident-classification {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
  margin: 2rem 0;
}

.severity-level {
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px solid var(--vp-c-divider);
}

.severity-level.critical {
  background: #fee;
  border-color: #f56565;
}

.severity-level.high {
  background: #fef5e7;
  border-color: #ed8936;
}

.severity-level.medium {
  background: #fefdf9;
  border-color: #d69e2e;
}

.severity-level.low {
  background: #f0fff4;
  border-color: #38a169;
}

.severity-level h4 {
  margin: 0 0 1rem 0;
  color: var(--vp-c-text-1);
}

.severity-level ul {
  margin: 0 0 1rem 0;
  padding-left: 1.5rem;
}

.severity-level strong {
  color: var(--vp-c-brand);
}

.incident-process {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
  margin: 2rem 0;
}

.process-step {
  padding: 1.5rem;
  background: var(--vp-c-bg-soft);
  border-radius: 8px;
  border: 1px solid var(--vp-c-divider);
  position: relative;
}

.process-step h4 {
  margin: 0 0 1rem 0;
  color: var(--vp-c-brand);
}

.process-step ul {
  margin: 0;
  padding-left: 1.5rem;
}

.process-step li {
  margin: 0.5rem 0;
  font-size: 0.95rem;
}

.security-contact {
  margin: 2rem 0;
  padding: 2rem;
  background: var(--vp-c-bg-soft);
  border-radius: 12px;
  border: 1px solid var(--vp-c-divider);
}

.security-contact h4 {
  margin: 0 0 1.5rem 0;
  color: var(--vp-c-brand);
}

.contact-methods {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
  margin: 2rem 0;
}

.contact-method {
  padding: 1.5rem;
  background: var(--vp-c-bg);
  border-radius: 8px;
  border: 1px solid var(--vp-c-divider);
}

.contact-method strong {
  color: var(--vp-c-brand);
  display: block;
  margin-bottom: 0.5rem;
}

.contact-method a {
  color: var(--vp-c-brand);
  text-decoration: none;
  font-weight: 600;
}

.contact-method a:hover {
  text-decoration: underline;
}

.contact-method p {
  margin: 0.5rem 0 0 0;
  color: var(--vp-c-text-2);
  font-size: 0.95rem;
}

.response-commitment {
  margin: 2rem 0 0 0;
  padding: 1.5rem;
  background: var(--vp-c-bg);
  border-radius: 8px;
  border: 1px solid var(--vp-c-divider);
}

.response-commitment h5 {
  margin: 0 0 1rem 0;
  color: var(--vp-c-brand);
}

.response-commitment ul {
  margin: 0;
  padding-left: 1.5rem;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.5rem;
}

.response-commitment li {
  margin: 0.5rem 0;
}

.response-commitment strong {
  color: var(--vp-c-text-1);
}
</style>
