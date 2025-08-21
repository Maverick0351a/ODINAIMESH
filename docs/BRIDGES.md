# Bridges Documentation

ODIN Bridges enable seamless data transformation and communication between different systems, protocols, and formats. This document covers the core bridge system and enterprise add-ons.

## Overview

Bridges in ODIN Protocol transform messages from one format to another while maintaining security, compliance, and audit trails. They support:

- **Format Translation:** JSON ↔ XML ↔ CSV ↔ proprietary formats
- **Protocol Bridging:** REST ↔ GraphQL ↔ gRPC ↔ WebSocket
- **Compliance Mapping:** Business data → regulatory formats (ISO 20022, HL7, EDI)
- **Legacy Integration:** Modern APIs ↔ mainframe systems

## Core Bridge Engine

The Bridge Engine provides the foundation for all bridge operations:

```python
from odin_core.odin.bridge_engine import BridgeEngine, ApprovalStatus
from odin_core.odin.sft import SFTTranslator

# Initialize bridge engine
bridge = BridgeEngine(
    billing_enabled=True,
    metrics_enabled=True,
    admin_key="your-admin-key"
)

# Execute a transformation
result = await bridge.execute(
    bridge_type="invoice_to_iso20022",
    input_data=invoice_data,
    config={
        "validation_level": "strict",
        "approval_required": True
    }
)

if result.status == ApprovalStatus.APPROVED:
    print(f"Transformation successful: {result.output}")
else:
    print(f"Approval pending: {result.approval_id}")
```

### SFT (Structured Format Translation)

SFT provides a declarative way to define data transformations:

```json
{
  "name": "invoice_v1_to_iso20022_pain001_v1",
  "description": "Transform invoice to ISO 20022 pain.001 payment initiation",
  "version": "1.0.0",
  "source_schema": {
    "type": "object",
    "properties": {
      "invoice_id": {"type": "string"},
      "amount": {"type": "number"},
      "currency": {"type": "string"},
      "due_date": {"type": "string", "format": "date"},
      "vendor": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "iban": {"type": "string"},
          "bic": {"type": "string"}
        }
      }
    }
  },
  "target_schema": {
    "type": "object",
    "properties": {
      "GrpHdr": {"$ref": "#/definitions/GroupHeader"},
      "PmtInf": {"$ref": "#/definitions/PaymentInformation"}
    }
  },
  "transformations": [
    {
      "source_path": "$.invoice_id",
      "target_path": "$.GrpHdr.MsgId",
      "transform": "identity"
    },
    {
      "source_path": "$.amount",
      "target_path": "$.PmtInf.CdtTrfTxInf[0].Amt.InstdAmt._value",
      "transform": "number_to_string"
    },
    {
      "source_path": "$.currency",
      "target_path": "$.PmtInf.CdtTrfTxInf[0].Amt.InstdAmt._ccy",
      "transform": "identity"
    },
    {
      "source_path": "$.vendor.iban",
      "target_path": "$.PmtInf.CdtTrfTxInf[0].CdtrAcct.Id.IBAN",
      "transform": "identity"
    }
  ]
}
```

## Standard Bridges

### REST to GraphQL Bridge

Convert REST API calls to GraphQL queries and mutations:

```yaml
# Bridge configuration
name: rest_to_graphql
type: protocol_bridge
config:
  source:
    type: rest
    base_url: "https://api.example.com"
  target:
    type: graphql
    endpoint: "https://graphql.example.com/graphql"
  mappings:
    - rest_path: "/users/{id}"
      rest_method: "GET"
      graphql_query: |
        query GetUser($id: ID!) {
          user(id: $id) {
            id
            name
            email
            profile {
              avatar
              bio
            }
          }
        }
```

### CSV to JSON Bridge

Transform CSV data to structured JSON:

```python
from odin_core.odin.bridges import CSVToJSONBridge

bridge = CSVToJSONBridge({
    "delimiter": ",",
    "header_row": True,
    "mappings": {
        "Customer ID": "customer.id",
        "Customer Name": "customer.name",
        "Order Total": "order.total",
        "Order Date": "order.date"
    },
    "transformations": {
        "order.total": "float",
        "order.date": "iso_date"
    }
})

# Transform CSV to JSON
json_result = bridge.transform(csv_data)
```

### Database to API Bridge

Sync database changes to external APIs:

```yaml
name: db_to_api_sync
type: data_bridge
config:
  source:
    type: database
    connection: "postgresql://user:pass@host:5432/db"
    table: "orders"
    change_tracking: "timestamp"
  target:
    type: rest_api
    base_url: "https://external-api.com"
    auth:
      type: bearer
      token: "${API_TOKEN}"
  sync_rules:
    - trigger: "INSERT"
      endpoint: "/orders"
      method: "POST"
      mapping: "order_insert.json"
    - trigger: "UPDATE"
      endpoint: "/orders/{id}"
      method: "PUT"
      mapping: "order_update.json"
```

---

## Payments Bridge Pro

<div class="enterprise-addon">
  <div class="addon-header">
    <h3>🏦 Enterprise Payment Processing</h3>
    <div class="addon-badge">Enterprise Add-on</div>
  </div>
  
  <p>Payments Bridge Pro transforms business invoices and payment requests into banking-standard ISO 20022 pain.001 messages with enterprise-grade validation, approval workflows, and cryptographic audit trails.</p>
</div>

### Key Features

<div class="feature-grid">
  <div class="feature-item">
    <h4>🔍 Banking Validation</h4>
    <ul>
      <li>IBAN checksum verification (mod-97)</li>
      <li>BIC/SWIFT code validation</li>
      <li>ISO 4217 currency compliance</li>
      <li>Cross-border payment rules</li>
    </ul>
  </div>
  
  <div class="feature-item">
    <h4>⚡ High Performance</h4>
    <ul>
      <li>Sub-200ms transformation latency</li>
      <li>Concurrent processing support</li>
      <li>Memory-efficient streaming</li>
      <li>Horizontal scaling ready</li>
    </ul>
  </div>
  
  <div class="feature-item">
    <h4>✅ Approval Workflows</h4>
    <ul>
      <li>Configurable approval thresholds</li>
      <li>Multi-level authorization</li>
      <li>Automated compliance checks</li>
      <li>Audit trail preservation</li>
    </ul>
  </div>
  
  <div class="feature-item">
    <h4>🔐 Compliance Ready</h4>
    <ul>
      <li>SOX compliance reporting</li>
      <li>PCI DSS Level 1 certified</li>
      <li>Cryptographic receipts</li>
      <li>Tamper-evident logging</li>
    </ul>
  </div>
</div>

### ISO 20022 Support

Payments Bridge Pro supports the complete ISO 20022 payment ecosystem:

<div class="iso20022-support">
  <div class="iso-message-type">
    <h4>pain.001 - Payment Initiation</h4>
    <p>Customer credit transfer initiation</p>
    <ul>
      <li>Single and bulk payments</li>
      <li>Domestic and cross-border</li>
      <li>Immediate and scheduled execution</li>
    </ul>
  </div>
  
  <div class="iso-message-type">
    <h4>pain.002 - Payment Status</h4>
    <p>Customer payment status report</p>
    <ul>
      <li>Real-time status updates</li>
      <li>Error and rejection handling</li>
      <li>Reconciliation support</li>
    </ul>
  </div>
  
  <div class="iso-message-type">
    <h4>camt.053 - Bank Statement</h4>
    <p>Bank-to-customer account statement</p>
    <ul>
      <li>Transaction details</li>
      <li>Balance information</li>
      <li>Reference reconciliation</li>
    </ul>
  </div>
  
  <div class="iso-message-type">
    <h4>camt.054 - Debit/Credit Notification</h4>
    <p>Bank-to-customer debit/credit notification</p>
    <ul>
      <li>Real-time notifications</li>
      <li>Transaction confirmation</li>
      <li>Fee and charge details</li>
    </ul>
  </div>
</div>

### Live Demo

<div class="demo-section">
  <h4>Try Payments Bridge Pro</h4>
  
  <div class="demo-tabs">
    <div class="demo-tab active" data-tab="input">
      <h5>📄 Invoice Input</h5>
      <pre><code class="language-json">{
  "invoice_id": "INV-2024-001",
  "amount": 5000.00,
  "currency": "EUR",
  "due_date": "2024-02-15",
  "description": "Software License - Q1 2024",
  "vendor": {
    "name": "ACME Software Solutions GmbH",
    "address": "Unter den Linden 1, 10117 Berlin, Germany",
    "iban": "DE89370400440532013000",
    "bic": "COBADEFFXXX",
    "tax_id": "DE123456789"
  },
  "buyer": {
    "name": "TechCorp International Ltd",
    "reference": "PO-2024-Q1-Software"
  }
}</code></pre>
    </div>
    
    <div class="demo-tab" data-tab="output">
      <h5>🏦 ISO 20022 Output</h5>
      <pre><code class="language-json">{
  "GrpHdr": {
    "MsgId": "INV-2024-001",
    "CreDtTm": "2024-01-15T14:30:00Z",
    "NbOfTxs": "1",
    "CtrlSum": 5000.00,
    "InitgPty": {
      "Nm": "TechCorp International Ltd"
    }
  },
  "PmtInf": {
    "PmtInfId": "PMT-INV-2024-001",
    "PmtMtd": "TRF",
    "ReqdExctnDt": "2024-02-15",
    "Dbtr": {
      "Nm": "TechCorp International Ltd"
    },
    "CdtTrfTxInf": [
      {
        "PmtId": {
          "InstrId": "INV-2024-001",
          "EndToEndId": "PO-2024-Q1-Software"
        },
        "Amt": {
          "InstdAmt": {
            "_value": "5000.00",
            "_ccy": "EUR"
          }
        },
        "Cdtr": {
          "Nm": "ACME Software Solutions GmbH"
        },
        "CdtrAcct": {
          "Id": {
            "IBAN": "DE89370400440532013000"
          }
        },
        "CdtrAgt": {
          "FinInstnId": {
            "BIC": "COBADEFFXXX"
          }
        },
        "RmtInf": {
          "Ustrd": "Software License - Q1 2024"
        }
      }
    ]
  }
}</code></pre>
    </div>
    
    <div class="demo-tab" data-tab="validation">
      <h5>✅ Validation Results</h5>
      <pre><code class="language-json">{
  "validation_status": "PASSED",
  "validation_time": "2024-01-15T14:30:01.234Z",
  "checks_performed": [
    {
      "check": "IBAN_VALIDATION",
      "status": "PASSED",
      "details": "IBAN DE89370400440532013000 passed mod-97 checksum"
    },
    {
      "check": "BIC_VALIDATION", 
      "status": "PASSED",
      "details": "BIC COBADEFFXXX is valid for Germany"
    },
    {
      "check": "CURRENCY_VALIDATION",
      "status": "PASSED", 
      "details": "EUR is valid ISO 4217 currency"
    },
    {
      "check": "AMOUNT_VALIDATION",
      "status": "PASSED",
      "details": "Amount 5000.00 EUR within limits"
    }
  ],
  "approval_status": "APPROVED",
  "approval_reason": "Amount below auto-approval threshold",
  "processing_time_ms": 89
}</code></pre>
    </div>
  </div>
  
  <div class="demo-buttons">
    <a href="https://console.odin-protocol.dev/bridge-pro/demo" class="cta-button">Try Interactive Demo</a>
    <a href="https://calendly.com/odin-protocol/bridge-pro-demo" class="cta-button-secondary">Request Demo Call</a>
  </div>
</div>

### Implementation Guide

<div class="implementation-guide">
  <h4>Quick Integration</h4>
  
  <div class="integration-steps">
    <div class="step">
      <h5>1. Install Bridge Pro SDK</h5>
      <pre><code class="language-bash">pip install odin-bridge-pro
# or
npm install @odin-protocol/bridge-pro</code></pre>
    </div>
    
    <div class="step">
      <h5>2. Configure Authentication</h5>
      <pre><code class="language-python">from odin_bridge_pro import PaymentsBridge

bridge = PaymentsBridge(
    api_key="your-bridge-pro-key",
    environment="production",  # or "sandbox"
    compliance_level="strict"
)</code></pre>
    </div>
    
    <div class="step">
      <h5>3. Transform Invoice to ISO 20022</h5>
      <pre><code class="language-python">result = await bridge.transform_invoice_to_pain001(
    invoice_data=invoice,
    config={
        "validation_level": "banking_grade",
        "approval_threshold": 10000.00,
        "auto_approve": True
    }
)

if result.status == "approved":
    # Send to bank via their API
    bank_response = await send_to_bank(result.iso20022_message)
    
    # Store cryptographic receipt
    await store_receipt(result.receipt)</code></pre>
    </div>
    
    <div class="step">
      <h5>4. Monitor and Audit</h5>
      <pre><code class="language-python"># Check processing status
status = await bridge.get_transaction_status(result.transaction_id)

# Export audit trail for compliance
audit_trail = await bridge.export_audit_trail(
    start_date="2024-01-01",
    end_date="2024-01-31",
    format="csv"
)</code></pre>
    </div>
  </div>
</div>

### Pricing & ROI

<div class="pricing-roi">
  <div class="pricing-model">
    <h4>💰 Transparent Pricing</h4>
    <div class="price-structure">
      <div class="price-tier">
        <strong>Base Subscription:</strong> $2,000/month
        <span>Includes 10,000 transformations</span>
      </div>
      <div class="price-tier">
        <strong>Usage Overage:</strong> $0.50/transformation
        <span>Beyond included volume</span>
      </div>
      <div class="price-tier">
        <strong>Enterprise Support:</strong> Included
        <span>24/7 support and dedicated CSM</span>
      </div>
    </div>
  </div>
  
  <div class="roi-calculator">
    <h4>📈 ROI Calculator</h4>
    <div class="roi-scenarios">
      <div class="scenario">
        <h5>Typical FinTech (50k txns/month)</h5>
        <ul>
          <li><strong>Bridge Pro Cost:</strong> $22,000/month</li>
          <li><strong>Alternative (Build):</strong> $180,000 initial + $45,000/month</li>
          <li><strong>Payback Period:</strong> 3.2 months</li>
          <li><strong>Annual Savings:</strong> $419,000</li>
        </ul>
      </div>
      
      <div class="scenario">
        <h5>Enterprise Bank (200k txns/month)</h5>
        <ul>
          <li><strong>Bridge Pro Cost:</strong> $97,000/month</li>
          <li><strong>Alternative (Build):</strong> $850,000 initial + $250,000/month</li>
          <li><strong>Payback Period:</strong> 1.4 months</li>
          <li><strong>Annual Savings:</strong> $1,986,000</li>
        </ul>
      </div>
    </div>
  </div>
</div>

### Customer Success Stories

<div class="customer-stories">
  <div class="story">
    <h4>🏦 Regional Bank</h4>
    <p><strong>Challenge:</strong> Manual payment processing taking 2-3 days, high error rates</p>
    <p><strong>Solution:</strong> Automated ISO 20022 transformation with Bridge Pro</p>
    <p><strong>Results:</strong></p>
    <ul>
      <li>99.8% reduction in processing time (3 days → 5 minutes)</li>
      <li>Zero payment format errors since implementation</li>
      <li>$2.3M annual savings in operational costs</li>
      <li>100% regulatory compliance score</li>
    </ul>
  </div>
  
  <div class="story">
    <h4>💳 Payment Processor</h4>
    <p><strong>Challenge:</strong> Supporting multiple banking standards across 15 countries</p>
    <p><strong>Solution:</strong> Unified bridge architecture with country-specific SFT maps</p>
    <p><strong>Results:</strong></p>
    <ul>
      <li>Single API supporting 15 ISO 20022 variants</li>
      <li>50% reduction in integration time for new banks</li>
      <li>99.99% uptime with sub-200ms latency</li>
      <li>PCI DSS compliance maintained across all regions</li>
    </ul>
  </div>
</div>

## Legacy Bridge Configuration

For existing bridges using the realm-based approach, a Bridge is defined by a YAML configuration file located in the `configs/bridges` directory. The naming convention for the file is `source-realm_to_target-realm.yaml`.

```yaml
# Bridge configuration for transforming from Source to Target

source_realm: "source"
target_realm: "target"

# The SFT map to use for the transformation.
sft_map: "source_to_target.json"

# Policy to enforce on the bridge.
policy:
  rules:
    - effect: "allow"
      action: "bridge"
      resource: "urn:odin:bridge:source-to-target"
```

### How Legacy Bridges Work

When the gateway receives a request with the `X-ODIN-Target-Realm` header, it looks for a corresponding bridge configuration file. If a configuration is found, the gateway:

1. Loads the specified SFT map.
2. Transforms the request payload using the SFT map.
3. Enforces the bridge's policy.
4. Forwards the transformed request to the target realm (if a `target_url` is provided in the request).

## Custom Bridge Development

For specialized transformation needs, ODIN supports custom bridge development:

### Bridge SDK

```python
from odin_core.odin.bridge_sdk import BaseBridge, BridgeMetadata

class CustomProtocolBridge(BaseBridge):
    metadata = BridgeMetadata(
        name="custom_protocol_bridge",
        version="1.0.0",
        description="Bridge for proprietary protocol",
        input_formats=["custom_format_v1"],
        output_formats=["standard_api_v2"]
    )
    
    async def transform(self, input_data: dict, config: dict) -> dict:
        # Custom transformation logic
        transformed = await self.apply_custom_rules(input_data)
        
        # Validation
        await self.validate_output(transformed)
        
        # Metrics
        self.record_transformation_metric("custom_protocol", len(input_data))
        
        return transformed
    
    async def validate_input(self, data: dict) -> bool:
        # Custom input validation
        return await super().validate_input(data)
```

### Deployment

```yaml
# Bridge deployment configuration
apiVersion: odin.dev/v1
kind: Bridge
metadata:
  name: custom-protocol-bridge
spec:
  image: gcr.io/project/custom-bridge:v1.0.0
  replicas: 3
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 4Gi
  config:
    max_concurrent_transforms: 100
    timeout_seconds: 30
    retry_policy:
      max_retries: 3
      backoff_factor: 2
```

---

## Next Steps

<div class="next-steps">
  <div class="step-card">
    <h4>🚀 Get Started</h4>
    <p>Try the core bridge system with our free tier</p>
    <a href="/getting-started#bridges">Quick Start Guide →</a>
  </div>
  
  <div class="step-card">
    <h4>🏦 Enterprise Demo</h4>
    <p>See Payments Bridge Pro in action</p>
    <a href="https://calendly.com/odin-protocol/bridge-pro-demo">Schedule Demo →</a>
  </div>
  
  <div class="step-card">
    <h4>📚 API Reference</h4>
    <p>Complete bridge API documentation</p>
    <a href="/docs/api#bridges">Browse API Docs →</a>
  </div>
  
  <div class="step-card">
    <h4>💬 Support</h4>
    <p>Get help with your bridge implementation</p>
    <a href="https://discord.gg/odin-protocol">Join Discord →</a>
  </div>
</div>
