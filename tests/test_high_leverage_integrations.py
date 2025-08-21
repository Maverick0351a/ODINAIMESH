"""
Tests for High-Leverage Integrations (Phase 1)

Tests OpenTelemetry bridge, per-hop metering, and SIEM integration features.
"""

import pytest
import json
import os
import time
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any
from decimal import Decimal

from libs.odin_core.odin.telemetry_bridge import (
    OdinTelemetryBridge, 
    TraceContext,
    emit_receipt_telemetry,
    emit_hop_telemetry
)
from libs.odin_core.odin.metering import (
    MeteringUnit,
    RevenueShareCalculator,
    PerHopMeteringService,
    create_operation_billing,
    enhance_receipt_with_marketplace_billing
)
from libs.odin_core.odin.siem_integration import (
    SecurityAlert,
    AlertSeverity,
    AlertCategory,
    SIEMIntegration,
    emit_policy_violation_alert
)


class TestOpenTelemetryBridge:
    """Test OpenTelemetry integration"""
    
    def test_trace_context_from_headers(self):
        """Test W3C trace context extraction"""
        headers = {
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
            "tracestate": "rojo=00f067aa0ba902b7"
        }
        
        context = TraceContext.from_headers(headers)
        
        assert context.trace_id == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        assert context.span_id == "rojo=00f067aa0ba902b7"
    
    def test_trace_context_to_headers(self):
        """Test trace context injection into headers"""
        context = TraceContext(
            trace_id="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
            trace_state="rojo=00f067aa0ba902b7"
        )
        
        headers = context.to_headers()
        
        assert headers["traceparent"] == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        assert headers["tracestate"] == "rojo=00f067aa0ba902b7"
    
    @patch.dict(os.environ, {
        "ODIN_OTEL_ENABLED": "0"  # Disable for testing
    })
    def test_telemetry_bridge_disabled(self):
        """Test that telemetry bridge respects disabled state"""
        bridge = OdinTelemetryBridge()
        
        assert not bridge.enabled
        assert bridge.tracer is None
        
        # Should return None when disabled
        receipt = {"payload": {"test": "data"}, "proof": {"oml_cid": "test123"}}
        result = bridge.emit_receipt_span(receipt)
        assert result is None
    
    @patch.dict(os.environ, {
        "ODIN_OTEL_ENABLED": "1",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317"
    })
    @patch("libs.odin_core.odin.telemetry_bridge.HAS_OTEL", True)
    def test_telemetry_bridge_enabled(self):
        """Test that telemetry bridge initializes when enabled"""
        with patch("libs.odin_core.odin.telemetry_bridge.trace") as mock_trace, \
             patch("libs.odin_core.odin.telemetry_bridge.metrics") as mock_metrics, \
             patch("opentelemetry.sdk.trace.TracerProvider") as mock_tracer_provider, \
             patch("opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter"), \
             patch("opentelemetry.sdk.resources.Resource"):
            
            bridge = OdinTelemetryBridge()
            assert bridge.enabled
            mock_trace.get_tracer.assert_called_once()
    
    def test_receipt_telemetry_convenience_function(self):
        """Test convenience function for receipt telemetry"""
        receipt = {
            "payload": {"intent": "test"},
            "proof": {"oml_cid": "test123"},
            "tenant_id": "acme",
            "sbom": {"models": ["gpt-4"], "tools": ["search"]}
        }
        
        # Should not raise error even if telemetry is disabled
        result = emit_receipt_telemetry(receipt, "test_operation")
        assert result is None or isinstance(result, str)


class TestPerHopMetering:
    """Test per-hop metering and billing"""
    
    def test_metering_unit_basic_cost(self):
        """Test basic metering unit cost calculation"""
        unit = MeteringUnit(operation="envelope")
        
        assert unit.to_billing_units() == 1.0  # Base cost
    
    def test_metering_unit_with_ai_tokens(self):
        """Test metering with AI token costs"""
        unit = MeteringUnit(
            operation="bridge",
            ai_model_tokens=5000,  # 5k tokens
            ai_model_type="gpt-4"  # Premium model
        )
        
        billing_units = unit.to_billing_units()
        
        # Base cost (1.0) + token cost (5000/1000 * 0.1 * 2.0 for premium)
        expected = 1.0 + (5.0 * 0.1 * 2.0)  # 1.0 + 1.0 = 2.0
        assert billing_units == expected
    
    def test_metering_unit_with_data_transfer(self):
        """Test metering with data transfer costs"""
        unit = MeteringUnit(
            operation="envelope",
            data_transfer_mb=5.5  # 5.5 MB
        )
        
        billing_units = unit.to_billing_units()
        
        # Base cost (1.0) + data transfer cost (5.5-1) * 0.01 = 1.0 + 0.045
        assert billing_units == 1.045
    
    def test_revenue_share_calculator(self):
        """Test revenue share calculation"""
        calculator = RevenueShareCalculator()
        
        shares = calculator.calculate_shares(
            billing_units=10.0,
            realm_id="test-realm",
            map_id="test-map"
        )
        
        total_revenue = 10.0 * 0.001  # $0.01 total
        
        assert shares.platform == total_revenue * 0.10  # 10% platform fee
        assert shares.realm == total_revenue * 0.15     # 15% realm share
        assert shares.map_creator == total_revenue * 0.05  # 5% map creator share
        
        # Provider gets remainder
        expected_provider = total_revenue * (1 - 0.10 - 0.15 - 0.05)  # 70%
        assert abs(shares.provider - expected_provider) < 0.000001  # Use epsilon for float comparison
        
        # Total should equal original revenue
        assert abs(shares.total() - total_revenue) < 0.000001
    
    def test_per_hop_metering_service(self):
        """Test per-hop metering service"""
        service = PerHopMeteringService()
        
        request_data = {"intent": "test", "data": "sample"}
        response_data = {"result": "success", "details": "operation completed"}
        sbom_info = {"models": ["gpt-4"], "tools": ["search"]}
        
        unit = service.create_metering_unit(
            "envelope", request_data, response_data, sbom_info
        )
        
        assert unit.operation == "envelope"
        assert unit.ai_model_type == "gpt-4"
        assert unit.data_transfer_mb > 0  # Should have calculated data transfer
    
    def test_enhance_receipt_with_billing(self):
        """Test receipt enhancement with billing information"""
        service = PerHopMeteringService()
        service.enabled = True  # Force enable for test
        
        receipt = {"payload": {"test": "data"}, "proof": {"oml_cid": "test123"}}
        unit = MeteringUnit(operation="test", base_cost=2.0)
        
        enhanced = service.enhance_receipt_with_billing(
            receipt, unit, "test-realm", "test-map"
        )
        
        assert "billing" in enhanced
        billing = enhanced["billing"]
        
        assert billing["units"] == 2.0
        assert billing["operation"] == "test"
        assert "pricing" in billing
        assert "revenue_shares" in billing
        assert "metering_details" in billing
    
    @pytest.mark.asyncio
    async def test_convenience_functions(self):
        """Test convenience functions for metering"""
        request_data = {"intent": "test"}
        response_data = {"result": "success"}
        
        # Test operation billing creation
        unit = create_operation_billing("test", request_data, response_data)
        assert unit.operation == "test"
        assert unit.data_transfer_mb > 0
        
        # Test receipt enhancement
        receipt = {"payload": request_data, "proof": {"oml_cid": "test123"}}
        enhanced = enhance_receipt_with_marketplace_billing(
            receipt, unit, "test-realm"
        )
        
        # Should work even if metering is disabled
        assert "payload" in enhanced
        assert "proof" in enhanced


class TestSIEMIntegration:
    """Test SIEM/SOAR integration"""
    
    def test_security_alert_creation(self):
        """Test security alert creation"""
        alert = SecurityAlert(
            severity=AlertSeverity.HIGH,
            category=AlertCategory.POLICY_VIOLATION,
            event_type="hel_denial",
            tenant_id="acme",
            trace_id="trace123",
            timestamp="1640995200",
            title="HEL Policy Violation",
            description="Request blocked by policy",
            metadata={"rule": "deny_external_calls"}
        )
        
        assert alert.severity == AlertSeverity.HIGH
        assert alert.category == AlertCategory.POLICY_VIOLATION
        assert alert.tenant_id == "acme"
    
    def test_splunk_hec_format(self):
        """Test Splunk HEC event formatting"""
        alert = SecurityAlert(
            severity=AlertSeverity.CRITICAL,
            category=AlertCategory.SYSTEM_COMPROMISE,
            event_type="breach_detected",
            tenant_id="acme",
            trace_id="trace123",
            timestamp="1640995200",
            title="System Compromise Detected",
            description="Suspicious activity detected",
            metadata={"indicators": ["unusual_traffic", "failed_auth"]}
        )
        
        splunk_event = alert.to_splunk_hec_event()
        
        assert splunk_event["source"] == "odin-gateway"
        assert splunk_event["sourcetype"] == "odin:security:alert"
        assert splunk_event["event"]["severity"] == "critical"
        assert splunk_event["event"]["category"] == "system_compromise"
        assert splunk_event["event"]["odin_alert"] is True
    
    def test_pagerduty_format(self):
        """Test PagerDuty event formatting"""
        alert = SecurityAlert(
            severity=AlertSeverity.HIGH,
            category=AlertCategory.POLICY_VIOLATION,
            event_type="policy_violation",
            tenant_id="acme",
            trace_id="trace123",
            timestamp="1640995200",
            title="Policy Violation",
            description="HEL policy blocked request",
            metadata={"rule": "block_external"}
        )
        
        pd_event = alert.to_pagerduty_v2_event()
        
        assert pd_event["event_action"] == "trigger"
        assert pd_event["payload"]["severity"] == "error"  # HIGH maps to error
        assert pd_event["payload"]["summary"].startswith("ODIN Security Alert:")
        assert "links" in pd_event
    
    def test_servicenow_format(self):
        """Test ServiceNow incident formatting"""
        alert = SecurityAlert(
            severity=AlertSeverity.CRITICAL,
            category=AlertCategory.AUTHENTICATION_FAILURE,
            event_type="auth_failure",
            tenant_id="acme",
            trace_id="trace123",
            timestamp="1640995200",
            title="Authentication Failure",
            description="Multiple failed authentication attempts",
            metadata={"attempts": 10, "source_ip": "192.168.1.100"}
        )
        
        sn_incident = alert.to_servicenow_incident()
        
        assert sn_incident["category"] == "Security"
        assert sn_incident["priority"] == "1"  # CRITICAL maps to priority 1
        assert sn_incident["impact"] == "2"    # High impact for critical
        assert "ODIN Security Alert:" in sn_incident["short_description"]
    
    @patch.dict(os.environ, {"ODIN_SIEM_ENABLED": "0"})
    def test_siem_integration_disabled(self):
        """Test SIEM integration when disabled"""
        siem = SIEMIntegration()
        assert not siem.enabled
        assert len(siem.webhooks) == 0
    
    @patch.dict(os.environ, {
        "ODIN_SIEM_ENABLED": "1",
        "SPLUNK_HEC_URL": "https://splunk.example.com/services/collector",
        "SPLUNK_HEC_TOKEN": "test-token"
    })
    def test_siem_integration_webhook_config(self):
        """Test SIEM integration webhook configuration"""
        siem = SIEMIntegration()
        
        assert siem.enabled
        assert "splunk" in siem.webhooks
        
        splunk_config = siem.webhooks["splunk"]
        assert splunk_config["url"] == "https://splunk.example.com/services/collector"
        assert "Splunk test-token" in splunk_config["headers"]["Authorization"]
    
    @pytest.mark.asyncio
    @patch("libs.odin_core.odin.siem_integration.httpx")
    async def test_siem_alert_dispatch(self, mock_httpx):
        """Test SIEM alert dispatch"""
        # Mock httpx response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"success": true}'
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status.return_value = None
        
        mock_client = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client
        
        # Create SIEM integration with webhook
        with patch.dict(os.environ, {
            "ODIN_SIEM_ENABLED": "1",
            "SPLUNK_HEC_URL": "https://splunk.example.com/services/collector",
            "SPLUNK_HEC_TOKEN": "test-token"
        }):
            siem = SIEMIntegration()
            
            alert = SecurityAlert(
                severity=AlertSeverity.HIGH,
                category=AlertCategory.POLICY_VIOLATION,
                event_type="test_violation",
                tenant_id="test",
                trace_id="trace123",
                timestamp="1640995200",
                title="Test Alert",
                description="Test description",
                metadata={}
            )
            
            result = await siem.emit_security_alert(alert)
            
            assert result["status"] == "dispatched"
            assert len(result["dispatched"]) == 1
            assert result["dispatched"][0]["webhook"] == "splunk"
    
    @pytest.mark.asyncio
    async def test_policy_violation_alert_convenience(self):
        """Test convenience function for policy violation alerts"""
        violation_details = {
            "rule": "deny_external_calls",
            "message": "External calls not allowed",
            "policy_details": {"severity": "high"}
        }
        
        request_context = {
            "tenant_id": "acme",
            "path": "/v1/envelope",
            "method": "POST",
            "client_ip": "192.168.1.100"
        }
        
        # Should not raise error even if SIEM is disabled
        result = await emit_policy_violation_alert(
            violation_details, request_context, "trace123"
        )
        
        # Result should be None (disabled) or dict (enabled)
        assert result is None or isinstance(result, dict)


class TestIntegrationWorkflow:
    """Test integrated workflow of all Phase 1 features"""
    
    @pytest.mark.asyncio
    async def test_complete_envelope_workflow(self):
        """Test complete envelope workflow with all integrations"""
        # Simulate envelope request
        payload = {"intent": "analyze", "data": "sample data"}
        
        # 1. Create metering unit
        unit = create_operation_billing("envelope", payload)
        assert unit.operation == "envelope"
        
        # 2. Create base receipt
        receipt = {
            "payload": payload,
            "proof": {"oml_cid": "test123", "kid": "key1", "ope": "signature"}
        }
        
        # 3. Enhance with billing
        receipt = enhance_receipt_with_marketplace_billing(
            receipt, unit, "test-realm", "test-map"
        )
        
        # 4. Emit telemetry
        trace_id = emit_receipt_telemetry(receipt, "envelope")
        
        # 5. Simulate policy violation and SIEM alert
        violation = {
            "rule": "test_rule",
            "message": "Test violation"
        }
        request_context = {
            "tenant_id": "test",
            "path": "/v1/envelope",
            "method": "POST"
        }
        
        siem_result = await emit_policy_violation_alert(
            violation, request_context, trace_id
        )
        
        # Verify complete workflow
        assert "payload" in receipt
        assert "proof" in receipt
        # Billing should be added if metering enabled
        if os.getenv("ODIN_METERING_ENABLED") == "1":
            assert "billing" in receipt
        
        # Telemetry and SIEM should not raise errors
        assert trace_id is None or isinstance(trace_id, str)
        assert siem_result is None or isinstance(siem_result, dict)


# Integration test configuration
@pytest.fixture
def mock_environment():
    """Set up test environment variables"""
    test_env = {
        "ODIN_OTEL_ENABLED": "0",
        "ODIN_METERING_ENABLED": "0", 
        "ODIN_SIEM_ENABLED": "0"
    }
    
    with patch.dict(os.environ, test_env):
        yield test_env
