from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

REG = CollectorRegistry(auto_describe=True)

REQS = Counter(
    "agent_beta_http_requests_total",
    "agent-beta requests",
    ["path", "method"],
    registry=REG,
)
LAT = Histogram(
    "agent_beta_http_request_seconds",
    "agent-beta latency",
    ["path", "method"],
    registry=REG,
)

MET_HTTP_SIG_VERIFY = Counter(
    "odin_httpsig_verifications_total",
    "HTTP signature verifications",
    ["service", "outcome"],
    registry=REG,
)

__all__ = [
    "REG",
    "REQS",
    "LAT",
    "CONTENT_TYPE_LATEST",
    "generate_latest",
    "MET_HTTP_SIG_VERIFY",
]
