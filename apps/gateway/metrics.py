from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

# Single registry used by the gateway app and all its modules
REG = CollectorRegistry(auto_describe=True)

# HTTP request metrics (middleware-owned)
REQS = Counter(
    "odin_http_requests_total",
    "gateway requests",
    ["path", "method"],
    registry=REG,
)
LAT = Histogram(
    "odin_http_request_seconds",
    "gateway latency",
    ["path", "method"],
    registry=REG,
)

# Per-tenant request metrics (optional; labels include tenant)
TENANT_REQS = Counter(
    "odin_tenant_http_requests_total",
    "gateway requests per tenant",
    ["tenant", "path", "method"],
    registry=REG,
)
TENANT_LAT = Histogram(
    "odin_tenant_http_request_seconds",
    "gateway latency per tenant",
    ["tenant", "path", "method"],
    registry=REG,
)

# Per-tenant quota accounting
MET_TENANT_QUOTA_CONSUMED = Counter(
    "odin_tenant_quota_consumed_total",
    "units consumed against tenant quota (requests)",
    ["tenant"],
    registry=REG,
)
MET_TENANT_QUOTA_BLOCKED = Counter(
    "odin_tenant_quota_blocked_total",
    "requests blocked due to tenant quota exhaustion",
    ["tenant"],
    registry=REG,
)

# Transform receipts emitted across stages
MET_TRANSFORM_RCPTS = Counter(
    "odin_transform_receipts_total",
    "transform receipts emitted",
    ["stage", "map", "storage", "outcome"],
    registry=REG,
)

# Mesh hop receipts
MET_HOPS = Counter(
    "odin_hops_total",
    "mesh hop receipts persisted",
    ["route"],
    registry=REG,
)

# Policy violations blocked by middleware
MET_POLICY_VIOLATIONS = Counter(
    "odin_policy_violations_total",
    "policy violations blocked",
    ["rule", "route"],
    registry=REG,
)

# Bridge -> Agent Beta hop metrics
MET_BRIDGE_BETA_REQS = Counter(
    "odin_bridge_beta_requests_total",
    "outbound requests to Agent Beta",
    ["outcome"],
    registry=REG,
)
MET_BRIDGE_BETA_LAT = Histogram(
    "odin_bridge_beta_request_seconds",
    "latency of outbound requests to Agent Beta",
    ["outcome"],
    registry=REG,
)

# HTTP signature verifications (gateway service)
MET_HTTP_SIG_VERIFY = Counter(
    "odin_httpsig_verifications_total",
    "HTTP signature verifications",
    ["service", "outcome"],
    registry=REG,
)

# Receipt write failure counter (GCS/Firestore/local)
MET_RECEIPT_WRITE_FAIL = Counter(
    "odin_receipt_write_failures_total",
    "receipt write failures",
    ["kind"],
    registry=REG,
)

# Dynamic reload invocations
MET_DYNAMIC_RELOAD = Counter(
    "odin_dynamic_reload_total",
    "dynamic reload invocations",
    ["target"],
    registry=REG,
)

# VAI (Verifiable Agent Identity) metrics for 0.9.0-beta
MET_VAI_REQUESTS = Counter(
    "odin_vai_requests_total",
    "VAI agent verification requests",
    ["agent_id", "status", "path"],
    registry=REG,
)

# SBOM header metrics for 0.9.0-beta
MET_SBOM_HEADERS = Counter(
    "odin_sbom_headers_total",
    "SBOM headers processed",
    ["type"],  # model, tool, prompt_cid
    registry=REG,
)

__all__ = [
    "REG",
    "REQS",
    "LAT",
    "TENANT_REQS",
    "TENANT_LAT",
    "CONTENT_TYPE_LATEST",
    "generate_latest",
    "MET_TRANSFORM_RCPTS",
    "MET_POLICY_VIOLATIONS",
    "MET_BRIDGE_BETA_REQS",
    "MET_BRIDGE_BETA_LAT",
    "MET_HTTP_SIG_VERIFY",
    "MET_HOPS",
    "MET_RECEIPT_WRITE_FAIL",
    "MET_DYNAMIC_RELOAD",
    "MET_TENANT_QUOTA_CONSUMED",
    "MET_TENANT_QUOTA_BLOCKED",
    "MET_VAI_REQUESTS",
    "MET_SBOM_HEADERS",
]

# --- Aliases for ergonomic imports ---
# These alias names allow `from .metrics import bridge_beta_requests_total, ...` style imports
transform_receipts_total = MET_TRANSFORM_RCPTS
bridge_beta_requests_total = MET_BRIDGE_BETA_REQS
bridge_beta_latency_seconds = MET_BRIDGE_BETA_LAT
policy_violations_total = MET_POLICY_VIOLATIONS
http_sig_verifications_total = MET_HTTP_SIG_VERIFY
receipt_write_failures_total = MET_RECEIPT_WRITE_FAIL
dynamic_reload_total = MET_DYNAMIC_RELOAD
requests_total = REQS
request_latency_seconds = LAT
mesh_hops_total = MET_HOPS
tenant_requests_total = TENANT_REQS
tenant_request_latency_seconds = TENANT_LAT
tenant_quota_consumed_total = MET_TENANT_QUOTA_CONSUMED
tenant_quota_blocked_total = MET_TENANT_QUOTA_BLOCKED

# VAI metrics aliases
vai_requests_total = MET_VAI_REQUESTS

# SBOM metrics aliases  
sbom_headers_total = MET_SBOM_HEADERS

# Include aliases in exports
__all__ += [
    "transform_receipts_total",
    "bridge_beta_requests_total",
    "bridge_beta_latency_seconds",
    "policy_violations_total",
    "http_sig_verifications_total",
    "requests_total",
    "request_latency_seconds",
    "mesh_hops_total",
    "receipt_write_failures_total",
    "dynamic_reload_total",
    "tenant_requests_total",
    "tenant_request_latency_seconds",
    "tenant_quota_consumed_total",
    "tenant_quota_blocked_total",
    "vai_requests_total",
    "sbom_headers_total",
]
