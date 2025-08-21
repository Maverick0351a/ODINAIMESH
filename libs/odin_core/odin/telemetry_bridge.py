"""
OpenTelemetry Bridge for ODIN Protocol

Emit receipts as spans/events so Splunk/Datadog/Grafana can visualize chains instantly.
Converts ODIN receipts and hops into OpenTelemetry spans with full trace context.
"""

from __future__ import annotations

import os
import time
import json
import logging
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass
from contextlib import contextmanager

try:
    from opentelemetry import trace, metrics
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.trace import TracerProvider, Span
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.trace.status import Status, StatusCode
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    HAS_OTEL = True
except ImportError:
    HAS_OTEL = False
    trace = None
    metrics = None
    Span = None

_log = logging.getLogger(__name__)

@dataclass
class TraceContext:
    """Trace context extracted from request headers"""
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    trace_flags: Optional[str] = None
    trace_state: Optional[str] = None
    
    @classmethod
    def from_headers(cls, headers: Dict[str, str]) -> "TraceContext":
        """Extract W3C Trace Context from HTTP headers"""
        return cls(
            trace_id=headers.get("traceparent"),
            span_id=headers.get("tracestate"),
            trace_flags=headers.get("trace-flags"),
            trace_state=headers.get("tracestate")
        )
    
    def to_headers(self) -> Dict[str, str]:
        """Convert back to HTTP headers for propagation"""
        headers = {}
        if self.trace_id:
            headers["traceparent"] = self.trace_id
        if self.trace_state:
            headers["tracestate"] = self.trace_state
        return headers

class OdinTelemetryBridge:
    """
    Bridge ODIN receipts and operations to OpenTelemetry for enterprise observability.
    
    Features:
    - Receipt emission as structured spans
    - Trace context propagation across hops
    - Metrics for receipt throughput and latency
    - Integration with Splunk/Datadog/Grafana
    """
    
    def __init__(self, service_name: str = "odin-gateway"):
        self.service_name = service_name
        self.enabled = self._check_enabled()
        
        if self.enabled and HAS_OTEL:
            self._setup_tracing()
            self._setup_metrics()
        else:
            self.tracer = None
            self.meter = None
            
    def _check_enabled(self) -> bool:
        """Check if OpenTelemetry is enabled via environment"""
        return (
            HAS_OTEL and 
            os.getenv("ODIN_OTEL_ENABLED", "0") == "1" and
            bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
        )
    
    def _setup_tracing(self):
        """Initialize OpenTelemetry tracing with OTLP exporter"""
        if not HAS_OTEL:
            return
            
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        
        # Configure trace provider
        trace_provider = TracerProvider(
            resource=self._create_resource()
        )
        
        # Add OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", 
                              os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")),
            headers=self._get_otlp_headers()
        )
        
        span_processor = BatchSpanProcessor(otlp_exporter)
        trace_provider.add_span_processor(span_processor)
        
        trace.set_tracer_provider(trace_provider)
        self.tracer = trace.get_tracer(
            "odin.protocol",
            version="0.9.0-beta",
            schema_url="https://odinprotocol.dev/schemas/telemetry/v1"
        )
        
        _log.info(f"OpenTelemetry tracing initialized for {self.service_name}")
    
    def _setup_metrics(self):
        """Initialize OpenTelemetry metrics"""
        if not HAS_OTEL:
            return
            
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        
        otlp_metric_exporter = OTLPMetricExporter(
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
                              os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")),
            headers=self._get_otlp_headers()
        )
        
        metric_reader = PeriodicExportingMetricReader(
            exporter=otlp_metric_exporter,
            export_interval_millis=int(os.getenv("OTEL_METRIC_EXPORT_INTERVAL", "30000"))
        )
        
        metrics.set_meter_provider(
            MeterProvider(
                resource=self._create_resource(),
                metric_readers=[metric_reader]
            )
        )
        
        self.meter = metrics.get_meter("odin.protocol")
        
        # Create metrics
        self.receipt_counter = self.meter.create_counter(
            "odin_receipts_emitted_total",
            description="Total ODIN receipts emitted as telemetry spans",
            unit="1"
        )
        
        self.hop_latency = self.meter.create_histogram(
            "odin_hop_latency_seconds", 
            description="Latency of ODIN hops in telemetry spans",
            unit="s"
        )
    
    def _create_resource(self):
        """Create OpenTelemetry resource with ODIN-specific attributes"""
        if not HAS_OTEL:
            return None
            
        from opentelemetry.sdk.resources import Resource
        
        return Resource.create({
            "service.name": self.service_name,
            "service.version": "0.9.0-beta",
            "service.namespace": "odin",
            "odin.gateway.version": os.getenv("ODIN_VERSION", "0.9.0-beta"),
            "odin.tenant.default": os.getenv("ODIN_DEFAULT_TENANT", "default"),
            "deployment.environment": os.getenv("ODIN_ENVIRONMENT", "development")
        })
    
    def _get_otlp_headers(self) -> Dict[str, str]:
        """Get OTLP headers from environment"""
        headers = {}
        
        # Support Datadog API key
        if api_key := os.getenv("DD_API_KEY"):
            headers["DD-API-KEY"] = api_key
            
        # Support Splunk HEC token
        if hec_token := os.getenv("SPLUNK_HEC_TOKEN"):
            headers["Authorization"] = f"Splunk {hec_token}"
            
        # Support custom headers
        if custom_headers := os.getenv("OTEL_EXPORTER_OTLP_HEADERS"):
            for header in custom_headers.split(","):
                if "=" in header:
                    key, value = header.split("=", 1)
                    headers[key.strip()] = value.strip()
                    
        return headers
    
    def extract_trace_context(self, headers: Dict[str, str]) -> Optional[TraceContext]:
        """Extract W3C trace context from incoming request headers"""
        if not self.enabled:
            return None
            
        return TraceContext.from_headers(headers)
    
    def inject_trace_context(self, headers: Dict[str, str], context: Optional[TraceContext] = None) -> Dict[str, str]:
        """Inject trace context into outgoing request headers"""
        if not self.enabled or not context:
            return headers
            
        headers.update(context.to_headers())
        return headers
    
    @contextmanager
    def start_receipt_span(self, 
                          operation: str,
                          receipt: Dict[str, Any],
                          parent_context: Optional[TraceContext] = None):
        """Start a span for receipt emission with full ODIN context"""
        if not self.enabled or not self.tracer:
            yield None
            return
            
        span_name = f"odin.{operation}"
        
        with self.tracer.start_as_current_span(span_name) as span:
            try:
                # Add ODIN-specific attributes
                self._add_receipt_attributes(span, receipt)
                self._add_operation_attributes(span, operation)
                
                # Add trace context
                if parent_context:
                    self._add_trace_context_attributes(span, parent_context)
                
                yield span
                
                # Mark as successful
                span.set_status(Status(StatusCode.OK))
                
                # Record metrics
                if self.receipt_counter:
                    self.receipt_counter.add(1, {
                        "operation": operation,
                        "tenant_id": receipt.get("tenant_id", "unknown"),
                        "stage": receipt.get("stage", "unknown")
                    })
                    
            except Exception as e:
                if span:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                raise
    
    def emit_receipt_span(self, 
                         receipt: Dict[str, Any], 
                         operation: str = "receipt",
                         parent_context: Optional[TraceContext] = None) -> Optional[str]:
        """
        Emit a single receipt as an OpenTelemetry span.
        
        Returns the trace ID for linking in logs/alerts.
        """
        if not self.enabled:
            return None
            
        with self.start_receipt_span(operation, receipt, parent_context) as span:
            if span:
                # Add receipt payload as span event
                span.add_event(
                    "odin.receipt.emitted",
                    {
                        "receipt.size_bytes": len(json.dumps(receipt, separators=(",", ":"))),
                        "receipt.has_proof": "proof" in receipt,
                        "receipt.has_sbom": "sbom" in receipt,
                        "receipt.timestamp": time.time()
                    }
                )
                
                # Return trace ID for correlation
                trace_context = span.get_span_context()
                if trace_context:
                    return f"{trace_context.trace_id:032x}"
                    
        return None
    
    def emit_hop_span(self, 
                     hop_receipt: Dict[str, Any],
                     source_realm: str,
                     target_realm: str,
                     latency_seconds: float) -> Optional[str]:
        """Emit a mesh hop as a span with routing context"""
        if not self.enabled:
            return None
            
        with self.start_receipt_span("hop", hop_receipt) as span:
            if span:
                # Add hop-specific attributes
                span.set_attribute("odin.hop.source_realm", source_realm)
                span.set_attribute("odin.hop.target_realm", target_realm)
                span.set_attribute("odin.hop.latency_seconds", latency_seconds)
                span.set_attribute("odin.hop.route", hop_receipt.get("route", "unknown"))
                
                # Record hop latency metric
                if self.hop_latency:
                    self.hop_latency.record(latency_seconds, {
                        "source_realm": source_realm,
                        "target_realm": target_realm,
                        "route": hop_receipt.get("route", "unknown")
                    })
                
                # Add hop event
                span.add_event(
                    "odin.hop.completed",
                    {
                        "hop.latency_ms": latency_seconds * 1000,
                        "hop.success": True,
                        "hop.timestamp": time.time()
                    }
                )
                
                trace_context = span.get_span_context()
                if trace_context:
                    return f"{trace_context.trace_id:032x}"
                    
        return None
    
    def emit_policy_violation_span(self, 
                                  violation: Dict[str, Any],
                                  request_context: Dict[str, Any]) -> Optional[str]:
        """Emit policy violation as a high-severity span for SIEM integration"""
        if not self.enabled:
            return None
            
        with self.start_receipt_span("policy_violation", violation) as span:
            if span:
                # Mark as error
                span.set_status(Status(StatusCode.ERROR, "HEL Policy Violation"))
                
                # Add violation details
                span.set_attribute("odin.policy.rule", violation.get("rule", "unknown"))
                span.set_attribute("odin.policy.severity", "HIGH")
                span.set_attribute("odin.policy.tenant_id", request_context.get("tenant_id", "unknown"))
                span.set_attribute("odin.policy.route", request_context.get("route", "unknown"))
                span.set_attribute("odin.policy.blocked", True)
                
                # Add violation event for alerting
                span.add_event(
                    "odin.security.policy_violation",
                    {
                        "violation.rule": violation.get("rule"),
                        "violation.message": violation.get("message"),
                        "violation.severity": "HIGH",
                        "violation.timestamp": time.time(),
                        "request.path": request_context.get("path"),
                        "request.method": request_context.get("method")
                    }
                )
                
                trace_context = span.get_span_context()
                if trace_context:
                    return f"{trace_context.trace_id:032x}"
                    
        return None
    
    def _add_receipt_attributes(self, span: Span, receipt: Dict[str, Any]):
        """Add ODIN receipt attributes to span"""
        # Core receipt attributes
        if "proof" in receipt:
            proof = receipt["proof"]
            span.set_attribute("odin.proof.cid", proof.get("oml_cid", ""))
            span.set_attribute("odin.proof.kid", proof.get("kid", ""))
            
        # Tenant information
        span.set_attribute("odin.tenant.id", receipt.get("tenant_id", "unknown"))
        
        # Stage/operation
        span.set_attribute("odin.stage", receipt.get("stage", "unknown"))
        span.set_attribute("odin.route", receipt.get("route", "unknown"))
        
        # SBOM information (0.9.0-beta)
        if "sbom" in receipt:
            sbom = receipt["sbom"]
            if "models" in sbom:
                span.set_attribute("odin.sbom.models", ",".join(sbom["models"]))
            if "tools" in sbom:
                span.set_attribute("odin.sbom.tools", ",".join(sbom["tools"]))
            if "prompt_cids" in sbom:
                span.set_attribute("odin.sbom.prompt_cids", ",".join(sbom["prompt_cids"]))
                
        # VAI information (0.9.0-beta)
        if "agent_id" in receipt:
            span.set_attribute("odin.vai.agent_id", receipt["agent_id"])
            
        # Billing information (future)
        if "billing" in receipt:
            billing = receipt["billing"]
            span.set_attribute("odin.billing.units", billing.get("units", 0))
    
    def _add_operation_attributes(self, span: Span, operation: str):
        """Add operation-specific attributes"""
        span.set_attribute("odin.operation", operation)
        span.set_attribute("odin.service", self.service_name)
        span.set_attribute("odin.version", "0.9.0-beta")
    
    def _add_trace_context_attributes(self, span: Span, context: TraceContext):
        """Add trace context attributes for correlation"""
        if context.trace_id:
            span.set_attribute("odin.trace.parent_id", context.trace_id)
        if context.span_id:
            span.set_attribute("odin.trace.parent_span_id", context.span_id)


# Global instance for easy access
_global_bridge: Optional[OdinTelemetryBridge] = None

def get_telemetry_bridge() -> OdinTelemetryBridge:
    """Get or create the global telemetry bridge instance"""
    global _global_bridge
    if _global_bridge is None:
        _global_bridge = OdinTelemetryBridge()
    return _global_bridge

def emit_receipt_telemetry(receipt: Dict[str, Any], 
                          operation: str = "receipt",
                          trace_context: Optional[TraceContext] = None) -> Optional[str]:
    """Convenience function to emit receipt telemetry"""
    bridge = get_telemetry_bridge()
    return bridge.emit_receipt_span(receipt, operation, trace_context)

def emit_hop_telemetry(hop_receipt: Dict[str, Any],
                      source_realm: str,
                      target_realm: str, 
                      latency_seconds: float) -> Optional[str]:
    """Convenience function to emit hop telemetry"""
    bridge = get_telemetry_bridge()
    return bridge.emit_hop_span(hop_receipt, source_realm, target_realm, latency_seconds)

def emit_security_telemetry(violation: Dict[str, Any],
                           request_context: Dict[str, Any]) -> Optional[str]:
    """Convenience function to emit security event telemetry"""
    bridge = get_telemetry_bridge()
    return bridge.emit_policy_violation_span(violation, request_context)
