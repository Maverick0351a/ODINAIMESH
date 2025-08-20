# Service Level Agreement (SLA)

Availability
- 99.9% monthly for Gateway and Relay.

Latency targets (P95, excluding client/network):
- Gateway ≤ 300 ms
- Relay ≤ 200 ms

Support response times
- P1 (critical outage): response within 4 hours
- P2 (major degradation): response within 1 business day
- P3 (minor issue): response within 2 business days

Receipts retention
- Configurable; see Runbook for storage backends and lifecycle policies.

Notes
- Metrics measured via /metrics (Prometheus) and Cloud Monitoring.
