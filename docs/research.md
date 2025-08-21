# Research

Welcome to the **ODIN Research Engine** - run controlled experiments across models and maps with cryptographic receipts, BYOM support, and built-in benchmarks.

## Quick Start

1. **Create a Project** - Get your isolated sandbox with quotas
2. **Upload Dataset** - Drag & drop JSON/CSV files for testing  
3. **Run Experiments** - Compare models, maps, and policies with A/B testing
4. **Get Results** - Coverage, latency, cost analysis with receipt chains

<OdinPlayground />

## API Reference

### Projects

Create isolated project sandboxes with quotas and guardrails.

```bash
# Create project
curl -X POST https://gateway.odin-protocol.dev/v1/projects \
  -H "Content-Type: application/json" \
  -H "X-ODIN-Agent: your-agent-did" \
  -d '{
    "name": "My Research Project",
    "description": "Experimenting with payment processing models"
  }'
```

### BYOM Tokens

Mint short-lived tokens for your AI model credentials (never stored server-side).

```bash
# Mint BYOK token (15min TTL)
curl -X POST https://gateway.odin-protocol.dev/v1/byok/token \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "api_key": "sk-your-key-here"
  }'
```

### Experiments

Set up A/B testing with controlled rollout percentages.

```bash
# Create experiment
curl -X POST https://gateway.odin-protocol.dev/v1/experiments \
  -H "Content-Type: application/json" \
  -H "X-ODIN-Project-ID: proj_xxx" \
  -d '{
    "id": "model-comparison-v1",
    "variant": "B", 
    "goal": "Compare GPT-4 vs Gemini for payment processing",
    "rollout_pct": 10
  }'
```

### Datasets

Upload test data for benchmarking (JSON/CSV supported).

```bash
# Upload dataset
curl -X POST https://gateway.odin-protocol.dev/v1/datasets \
  -H "X-ODIN-Project-ID: proj_xxx" \
  -F "file=@invoices.json"
```

### Runs

Execute experiments with built-in evaluation.

```bash
# Run experiment
curl -X POST https://gateway.odin-protocol.dev/v1/runs \
  -H "Content-Type: application/json" \
  -H "X-ODIN-Project-ID: proj_xxx" \
  -d '{
    "experiment_id": "model-comparison-v1",
    "dataset_id": "ds_xxx",
    "realm": "business",
    "map_id": "iso20022_pain001_v1",
    "router_policy": "cost_optimized",
    "byok_token": "byok_xxx"
  }'
```

### Reports

Get detailed results with receipt chains for reproducibility.

```bash
# Get run report
curl https://gateway.odin-protocol.dev/v1/runs/run_xxx/report \
  -H "X-ODIN-Project-ID: proj_xxx"
```

Example response:
```json
{
  "run_id": "run_abc123",
  "status": "completed", 
  "metrics": {
    "coverage_pct": 95.2,
    "p95_latency_ms": 47.3,
    "cost_per_request": 0.0023,
    "success_rate": 0.998,
    "mediator_score": 0.87,
    "enum_violations": 0
  },
  "receipt_chain": [
    "bafybeiexample1...",
    "bafybeiexample2...", 
    "bafybeiexample3..."
  ]
}
```

### Receipts Export

Export all project receipts for analysis (headers redacted for security).

```bash
# Export receipts as NDJSON
curl "https://gateway.odin-protocol.dev/v1/receipts/export?project=proj_xxx&format=ndjson"

# Export as Parquet
curl "https://gateway.odin-protocol.dev/v1/receipts/export?project=proj_xxx&format=parquet"
```

## Built-in Evaluations

Every run includes automatic evaluation across multiple dimensions:

- **Translation Quality**: Coverage %, missing fields, enum violations, round-trip validation
- **Performance**: P50/P95 latency, cost per request by provider
- **Mediator Verdict**: Pass/warn/fail with reason codes (no chain-of-thought exposed)  
- **Receipt Continuity**: % runs with complete hop chain for reproducibility

## Safety & Guardrails

- **CORS Protection**: Only allowed domains can call BYOK routes
- **Rate Limiting**: 30 req/min for tokens, 10 req/min for runs
- **Realm Allowlist**: Free tier limited to `business` realm (no PII)
- **Header Redaction**: Auth tokens never persisted in logs/receipts
- **HEL Policies**: Payload limits, required headers, SSRF protection
- **Project Quotas**: Auto-pause on overage to prevent abuse

## Pricing Tiers

### Free Research
- 1 project
- 1,000 requests/month  
- BYOM only
- Basic benchmarks & receipts
- Business realm only

### Pro Research ($99/month)
- 3 projects
- 50,000 requests/month
- Router policies & optimization
- Data export (NDJSON/Parquet)  
- All realms access
- Mediator evaluation

### Enterprise
- Private tenant with SSO
- Custom SLOs & support
- Payments Bridge Pro access
- Dedicated infrastructure

## Examples

### Banking Payment Processing

Test ISO 20022 pain.001 transformation with multiple models:

```json
{
  "experiment_id": "iso20022-comparison",
  "dataset": [
    {
      "invoice_id": "INV-2024-001",
      "amount": 5000.00,
      "currency": "EUR",
      "vendor": {
        "name": "ACME Software GmbH", 
        "iban": "DE89370400440532013000",
        "bic": "COBADEFFXXX"
      }
    }
  ],
  "expected_coverage": ["DbtrAcct", "CdtrAcct", "InstdAmt"],
  "validation": "round_trip_xml_parse"
}
```

### Data Format Translation

Compare model performance on structured data transformation:

```json
{
  "experiment_id": "format-translation-v2",
  "variants": {
    "A": {"model": "gpt-4o-mini", "temperature": 0},
    "B": {"model": "gemini-1.5-flash", "temperature": 0}
  },
  "dataset": "csv_to_json_samples.csv",
  "metrics": ["accuracy", "schema_compliance", "cost"]
}
```

## Reproducibility

Every run generates a cryptographic receipt chain stored on IPFS:

1. **Input Receipt**: Dataset hash + experiment config
2. **Execution Receipt**: Model response + provider metadata  
3. **Evaluation Receipt**: Benchmark scores + validation results

Use any `trace_id` to reproduce exact results:

```bash
curl https://gateway.odin-protocol.dev/v1/receipts/trace/trace_abc123
```

## Community

- **Discord**: [discord.gg/odin-protocol](https://discord.gg/odin-protocol)
- **GitHub**: [github.com/odin-protocol/research](https://github.com/odin-protocol/research)
- **Example Datasets**: [github.com/odin-protocol/research-datasets](https://github.com/odin-protocol/research-datasets)

## FAQ

**Q: How are my API keys protected?**  
A: Keys are only used to mint short-lived (15min) tokens on our server. We never store your actual API keys.

**Q: Can I contribute test datasets?**  
A: Yes! Submit via GitHub with our Map Linter validation for community use.

**Q: What happens if I exceed my quota?**  
A: Projects auto-pause to prevent unexpected charges. Upgrade anytime via dashboard.

**Q: Are receipts truly immutable?**  
A: Yes, they're content-addressed on IPFS. Any change results in a different hash.

---

Ready to run your first experiment? [Create a project](/research#quick-start) and start testing!
