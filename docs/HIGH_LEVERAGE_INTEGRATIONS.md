# High-Leverage Integrations Roadmap

## 🎯 Strategic Implementation Plan

These are **stackable, pragmatic** integrations that will significantly increase ODIN's enterprise adoption and interoperability. Each can be implemented independently while building on existing foundation.

## 📋 Implementation Priority Matrix

| Integration | Complexity | Impact | Dependencies | Timeline |
|-------------|------------|---------|-------------|----------|
| **Provider Adapters** | Medium | Very High | SFT maps | 2-3 weeks |
| **OpenTelemetry Bridge** | Low | High | Existing metrics | 1 week |
| **Per-hop Metering** | Low | High | Billing system | 1 week |
| **HEL→OPA/Cedar Compiler** | High | Very High | HEL engine | 3-4 weeks |
| **Vault/KMS Integration** | Medium | High | Key management | 2 weeks |
| **SIEM/SOAR Hooks** | Low | Medium | Alert system | 1 week |
| **Map Synthesis CLI** | Medium | Medium | SFT maps | 2 weeks |
| **Data-minimization IFC** | High | Medium | SFT system | 3-4 weeks |

## 🚀 Phase 1: Quick Wins (1-2 weeks)

### 1. OpenTelemetry Bridge
**Goal:** Emit receipts as spans/events for instant visualization in Splunk/Datadog/Grafana

```python
# libs/odin_core/odin/telemetry_bridge.py
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

class OdinTelemetryBridge:
    def __init__(self):
        self.tracer = trace.get_tracer("odin.protocol")
        
    def emit_receipt_as_span(self, receipt: dict, parent_span=None):
        """Convert ODIN receipt to OpenTelemetry span with full context"""
        with self.tracer.start_as_current_span(
            f"odin.hop.{receipt.get('stage', 'unknown')}", 
            parent=parent_span
        ) as span:
            # Add receipt metadata as span attributes
            span.set_attribute("odin.proof.cid", receipt.get("proof", {}).get("oml_cid"))
            span.set_attribute("odin.hop.route", receipt.get("route"))
            span.set_attribute("odin.tenant.id", receipt.get("tenant_id"))
            if "sbom" in receipt:
                span.set_attribute("odin.sbom.models", ",".join(receipt["sbom"].get("models", [])))
                
    def create_trace_context(self, request_headers: dict) -> dict:
        """Extract OpenTelemetry context from incoming request"""
        # Handle W3C Trace Context headers
        return {
            "trace_id": request_headers.get("traceparent"),
            "span_id": request_headers.get("tracestate")
        }
```

**Integration Points:**
- Enhance existing receipt emission in `apps/gateway/envelope.py`
- Add trace context to mesh forwarding in `apps/gateway/bridge.py`
- Emit spans for policy violations and VAI validations

### 2. Per-hop Metering & Settlement
**Goal:** Extend receipts with billing.units + Stripe usage events

```python
# libs/odin_core/odin/metering.py
from dataclasses import dataclass
from typing import Optional, Dict, Any
from billing.usage import record_request_event

@dataclass
class MeteringUnit:
    """Billing unit for a single hop/operation"""
    operation: str  # envelope, transform, bridge, stream
    compute_cost: float  # normalized compute units
    data_transfer_mb: float
    storage_operations: int
    ai_model_tokens: Optional[int] = None
    
    def to_billing_units(self) -> float:
        """Convert to billable units (base: 1 unit = 1000 requests)"""
        base_cost = 1.0  # 1 unit per operation
        
        # Add compute overhead
        if self.ai_model_tokens:
            base_cost += (self.ai_model_tokens / 1000) * 0.1  # 0.1 units per 1k tokens
            
        # Add data transfer cost
        if self.data_transfer_mb > 1:
            base_cost += self.data_transfer_mb * 0.01  # 0.01 units per MB
            
        return base_cost

class RevenueShareCalculator:
    """Calculate marketplace revenue splits"""
    
    MARKETPLACE_FEE = 0.10  # 10% platform fee
    REALM_SHARE = 0.15      # 15% to realm owner
    MAP_SHARE = 0.05        # 5% to SFT map creator
    
    def calculate_shares(self, billing_units: float, realm_id: str, map_id: Optional[str] = None) -> Dict[str, float]:
        total_revenue = billing_units * self.get_unit_price()
        
        shares = {
            "platform": total_revenue * self.MARKETPLACE_FEE,
            "provider": total_revenue * (1 - self.MARKETPLACE_FEE - self.REALM_SHARE),
            "realm": total_revenue * self.REALM_SHARE
        }
        
        if map_id:
            shares["provider"] -= total_revenue * self.MAP_SHARE
            shares["map_creator"] = total_revenue * self.MAP_SHARE
            
        return shares
        
    def get_unit_price(self) -> float:
        """Current price per billing unit in USD"""
        return 0.001  # $0.001 per unit
```

**Integration:**
- Enhance receipt structure to include `billing: {units, revenue_shares}`
- Auto-report to Stripe when receipts are emitted
- Add marketplace revenue tracking dashboard

### 3. SIEM/SOAR Hooks
**Goal:** Push high-severity HEL denials/drift alerts with trace links

```python
# libs/odin_core/odin/siem_integration.py
import asyncio
import json
from typing import Dict, Any, List
from dataclasses import dataclass, asdict

@dataclass
class SecurityAlert:
    severity: str  # critical, high, medium, low
    category: str  # policy_violation, drift_detected, suspicious_activity
    event_type: str  # hel_denial, unauthorized_access, rate_limit_exceeded
    tenant_id: str
    trace_id: str
    timestamp: str
    metadata: Dict[str, Any]
    
    def to_splunk_event(self) -> Dict[str, Any]:
        """Format for Splunk HEC"""
        return {
            "time": self.timestamp,
            "source": "odin-gateway",
            "sourcetype": "odin:security",
            "index": "security",
            "event": {
                **asdict(self),
                "odin_alert": True
            }
        }
        
    def to_pagerduty_event(self) -> Dict[str, Any]:
        """Format for PagerDuty Events API v2"""
        return {
            "routing_key": os.getenv("PAGERDUTY_ROUTING_KEY"),
            "event_action": "trigger",
            "payload": {
                "summary": f"ODIN {self.severity.upper()}: {self.event_type}",
                "source": "odin-gateway",
                "severity": self.severity,
                "custom_details": self.metadata,
                "links": [{
                    "href": f"{os.getenv('ODIN_TRACE_URL')}/trace/{self.trace_id}",
                    "text": "View Full Trace"
                }]
            }
        }

class SIEMIntegration:
    def __init__(self):
        self.webhooks = self._load_webhook_config()
        self.alert_thresholds = self._load_thresholds()
        
    async def emit_security_alert(self, alert: SecurityAlert):
        """Dispatch alert to configured SIEM/SOAR systems"""
        tasks = []
        
        if "splunk" in self.webhooks:
            tasks.append(self._send_to_splunk(alert))
        if "pagerduty" in self.webhooks:
            tasks.append(self._send_to_pagerduty(alert))
        if "servicenow" in self.webhooks:
            tasks.append(self._send_to_servicenow(alert))
            
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
```

## 🔧 Phase 2: Core Infrastructure (2-3 weeks)

### 4. Provider Adapters 
**Goal:** Hardened connectors for all major AI providers with SFT normalization

```python
# libs/odin_core/odin/providers/
# Base provider interface
class BaseProvider:
    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Normalize across all providers"""
        pass
        
    async def normalize_with_sft(self, response: Any, sft_map: str) -> Dict[str, Any]:
        """Apply SFT transformation to provider response"""
        pass

# Implementations:
# - openai_provider.py    - OpenAI GPT models
# - anthropic_provider.py - Claude models  
# - vertex_provider.py    - Google Vertex AI/Gemini
# - bedrock_provider.py   - AWS Bedrock
# - azure_provider.py     - Azure OpenAI
# - mistral_provider.py   - Mistral AI
# - local_provider.py     - Local Llama/Ollama
```

**Features:**
- Unified authentication handling
- Rate limiting per provider
- Error handling and retries
- Cost optimization (model routing)
- SFT-based response normalization
- Automatic SBOM header injection

### 5. Vault/KMS Key Custody
**Goal:** Externalize key material and rotation; record in receipts

```python
# libs/odin_core/odin/key_custody.py
from typing import Optional, Dict, Any
import hashlib
from dataclasses import dataclass

@dataclass
class KeyMetadata:
    kid: str
    vault_path: str
    created_at: str
    expires_at: Optional[str]
    usage_count: int
    algorithm: str
    
class VaultKeyProvider:
    """HashiCorp Vault integration for key custody"""
    
    def __init__(self, vault_url: str, vault_token: str):
        self.vault_url = vault_url
        self.vault_token = vault_token
        
    async def get_signing_key(self, kid: str) -> bytes:
        """Retrieve private key from Vault"""
        # Vault API call with audit logging
        pass
        
    async def rotate_key(self, kid: str) -> KeyMetadata:
        """Generate new key and update metadata"""
        # Create new key in Vault
        # Update JWKS with new public key
        # Record rotation event in receipts
        pass
        
    def record_key_usage(self, kid: str, operation: str, success: bool):
        """Track key usage for audit/compliance"""
        pass

class CloudKMSProvider:
    """Google Cloud KMS integration"""
    
    async def sign_with_kms(self, kid: str, payload: bytes) -> bytes:
        """Sign using Cloud KMS with HSM backing"""
        pass
        
    async def create_key_version(self, key_ring: str, key_name: str) -> str:
        """Create new key version for rotation"""
        pass
```

## 🧠 Phase 3: Advanced Features (3-4 weeks)

### 6. HEL→OPA/Cedar Compiler
**Goal:** Export HEL to standard engines while keeping HEL as source of truth

```python
# libs/odin_core/odin/policy_compiler.py
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class PolicyRule:
    id: str
    condition: str
    action: str  # allow, deny
    resources: List[str]
    principals: List[str]

class HELToOPACompiler:
    """Compile HEL policies to Open Policy Agent Rego"""
    
    def compile_to_rego(self, hel_policy: Dict[str, Any]) -> str:
        """
        Convert HEL policy to OPA Rego format
        
        HEL: {"rules": [{"if": "tenant_id == 'acme'", "then": "allow"}]}
        OPA: allow = true { input.tenant_id == "acme" }
        """
        rego_rules = []
        
        for rule in hel_policy.get("rules", []):
            rego_rule = self._convert_rule(rule)
            rego_rules.append(rego_rule)
            
        return self._wrap_in_package(rego_rules)
        
    def _convert_rule(self, hel_rule: Dict[str, Any]) -> str:
        """Convert single HEL rule to Rego"""
        condition = hel_rule.get("if", "")
        action = hel_rule.get("then", "deny")
        
        # Convert HEL condition syntax to Rego
        rego_condition = self._convert_condition(condition)
        
        if action == "allow":
            return f"allow = true {{ {rego_condition} }}"
        else:
            return f"deny[reason] {{ {rego_condition}; reason := \"HEL rule violation\" }}"

class HELToCedarCompiler:
    """Compile HEL policies to Amazon Cedar"""
    
    def compile_to_cedar(self, hel_policy: Dict[str, Any]) -> str:
        """
        Convert HEL policy to Cedar format
        
        Cedar: permit(principal, action, resource) when { principal.tenant_id == "acme" };
        """
        cedar_policies = []
        
        for rule in hel_policy.get("rules", []):
            cedar_policy = self._convert_to_cedar(rule)
            cedar_policies.append(cedar_policy)
            
        return "\n\n".join(cedar_policies)
```

### 7. Data-minimization IFC
**Goal:** Label fields with lattice and propagate through SFT

```python
# libs/odin_core/odin/data_minimization.py
from enum import Enum
from typing import Dict, Any, Set, Optional
from dataclasses import dataclass

class DataLabel(Enum):
    """Information Flow Control labels (lattice)"""
    PUBLIC = 0      # Publicly shareable
    INTERNAL = 1    # Internal company use
    CONFIDENTIAL = 2 # Confidential data
    RESTRICTED = 3   # Highly restricted
    
    def can_flow_to(self, other: "DataLabel") -> bool:
        """Check if this label can flow to another (no upward flow)"""
        return self.value <= other.value

@dataclass
class LabeledField:
    """Field with associated data label"""
    path: str
    label: DataLabel
    metadata: Dict[str, Any]

class IFCProcessor:
    """Information Flow Control processor for SFT transformations"""
    
    def __init__(self):
        self.label_rules = self._load_label_rules()
        
    def label_input_data(self, data: Dict[str, Any]) -> Dict[str, LabeledField]:
        """Apply initial labels to input data based on rules"""
        labeled_fields = {}
        
        for path, value in self._flatten_dict(data):
            label = self._determine_label(path, value)
            labeled_fields[path] = LabeledField(path, label, {"original_value": value})
            
        return labeled_fields
        
    def propagate_labels(self, 
                        input_labels: Dict[str, LabeledField],
                        sft_operation: str,
                        output_data: Dict[str, Any]) -> Dict[str, LabeledField]:
        """Propagate labels through SFT transformation"""
        output_labels = {}
        
        # Get SFT mapping rules
        mapping = self._get_sft_mapping(sft_operation)
        
        for output_path, output_value in self._flatten_dict(output_data):
            # Find which input fields contributed to this output
            contributing_inputs = mapping.get(output_path, [])
            
            # Join labels (take highest/most restrictive)
            max_label = DataLabel.PUBLIC
            for input_path in contributing_inputs:
                if input_path in input_labels:
                    input_label = input_labels[input_path].label
                    if input_label.value > max_label.value:
                        max_label = input_label
                        
            output_labels[output_path] = LabeledField(
                output_path, 
                max_label,
                {"contributing_inputs": contributing_inputs}
            )
            
        return output_labels
        
    def generate_label_receipt(self, 
                             input_labels: Dict[str, LabeledField],
                             output_labels: Dict[str, LabeledField]) -> Dict[str, Any]:
        """Generate receipt showing label propagation"""
        return {
            "data_minimization": {
                "input_labels": {k: {"path": v.path, "label": v.label.name} for k, v in input_labels.items()},
                "output_labels": {k: {"path": v.path, "label": v.label.name} for k, v in output_labels.items()},
                "label_joins": self._compute_label_joins(input_labels, output_labels),
                "compliance_check": self._verify_compliance(output_labels)
            }
        }
```

### 8. Map Synthesis & Verification CLI
**Goal:** LLM-drafted SFT maps with property testing

```python
# tools/map_synthesis.py
from typing import Dict, Any, List
import json
from dataclasses import dataclass

@dataclass
class SFTMapSpec:
    """Specification for generating SFT map"""
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    transformation_description: str
    examples: List[Dict[str, Any]]

class MapSynthesizer:
    """Generate SFT maps using LLM with verification"""
    
    def __init__(self, llm_provider: str = "gpt-4"):
        self.llm_provider = llm_provider
        
    async def synthesize_map(self, spec: SFTMapSpec) -> Dict[str, Any]:
        """Generate SFT map from specification"""
        prompt = self._build_synthesis_prompt(spec)
        
        # Call LLM to generate map
        generated_map = await self._call_llm(prompt)
        
        # Verify generated map
        verification_result = self._verify_map(generated_map, spec)
        
        if not verification_result.is_valid:
            # Iterate to fix issues
            generated_map = await self._fix_map_issues(generated_map, verification_result, spec)
            
        return generated_map
        
    def _verify_map(self, sft_map: Dict[str, Any], spec: SFTMapSpec) -> "VerificationResult":
        """Property-test the generated map"""
        issues = []
        
        # Test invertibility
        if not self._test_invertibility(sft_map):
            issues.append("Map is not invertible")
            
        # Test required field coverage
        if not self._test_field_coverage(sft_map, spec):
            issues.append("Missing required field mappings")
            
        # Test with examples
        for example in spec.examples:
            if not self._test_example(sft_map, example):
                issues.append(f"Failed on example: {example}")
                
        return VerificationResult(len(issues) == 0, issues)
        
    def _test_invertibility(self, sft_map: Dict[str, Any]) -> bool:
        """Test if map can be inverted (forward -> backward -> original)"""
        # Property: transform(inverse_transform(x)) == x
        pass
        
    def _test_field_coverage(self, sft_map: Dict[str, Any], spec: SFTMapSpec) -> bool:
        """Ensure all required fields are mapped"""
        # Check that all required output fields have mappings
        pass

# CLI tool
if __name__ == "__main__":
    import asyncio
    import click
    
    @click.command()
    @click.option("--spec-file", required=True, help="SFT map specification JSON")
    @click.option("--output", required=True, help="Output SFT map file")
    @click.option("--verify-only", is_flag=True, help="Only verify existing map")
    async def synthesize_map(spec_file: str, output: str, verify_only: bool):
        """Synthesize and verify SFT maps"""
        pass
```

## 🔄 Integration Points

### Enhanced Receipt Structure
```json
{
  "payload": {...},
  "proof": {"oml_cid": "...", "ope": "..."},
  "sbom": {"models": [...], "tools": [...]},
  "billing": {
    "units": 1.25,
    "revenue_shares": {
      "platform": 0.125,
      "provider": 1.0,
      "realm": 0.125
    }
  },
  "telemetry": {
    "trace_id": "a1b2c3...",
    "span_id": "d4e5f6..."
  },
  "security": {
    "key_custody": {
      "kid": "vault://keys/odin-2024-q4",
      "usage_count": 1247
    },
    "data_labels": {
      "input_max": "CONFIDENTIAL",
      "output_max": "INTERNAL"
    }
  },
  "policy": {
    "engine": "opa",
    "policy_version": "v1.2.3",
    "evaluation_time_ms": 12
  }
}
```

## 📊 Implementation Success Metrics

### Phase 1 Success Criteria
- [ ] OpenTelemetry spans appear in Grafana/Datadog within 30 seconds
- [ ] Stripe usage events auto-reported with <1% error rate
- [ ] Security alerts trigger in PagerDuty within 60 seconds

### Phase 2 Success Criteria  
- [ ] All 7 provider adapters pass integration tests
- [ ] Key rotation from Vault completes in <30 seconds
- [ ] Provider fallback works with <500ms latency penalty

### Phase 3 Success Criteria
- [ ] HEL→OPA compilation achieves 100% policy coverage
- [ ] Map synthesis generates valid maps 95% of time
- [ ] Data label propagation maintains correctness across all SFT operations

## 🚀 Getting Started

1. **Choose Phase 1 integration** based on immediate needs
2. **Set up feature flags** for gradual rollout
3. **Implement with existing patterns** (middleware, metrics, receipts)
4. **Test with current 0.9.0-beta features** for compatibility
5. **Document integration points** for marketplace users

Each integration builds on the solid foundation we've established and follows ODIN's design principles for stackable, enterprise-ready features! 🎯
