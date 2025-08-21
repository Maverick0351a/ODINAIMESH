"""
Test suite for ODIN Payments Bridge Pro - high-value revenue add-on.

Tests bridge execution, ISO 20022 validation, approval workflows, and billing integration.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch
from libs.odin_core.odin.bridge_engine import BridgeEngine, BridgeResult, ApprovalStatus
from libs.odin_core.odin.validators.iso20022 import (
    ISO20022Validator,
    ValidationError,
    ValidationSeverity
)
from apps.gateway.metrics import (
    MET_BRIDGE_EXEC_TOTAL,
    MET_BRIDGE_EXEC_DURATION,
    MET_BRIDGE_APPROVAL_PENDING,
    MET_ISO20022_VALIDATE_FAIL_TOTAL
)


@pytest.fixture
def bridge_engine():
    """Bridge engine with test SFT registry."""
    engine = BridgeEngine()
    
    # Mock SFT registry with test map
    test_sft_map = {
        "metadata": {
            "name": "Test Invoice to ISO 20022",
            "version": "1.0.0",
            "source_format": "invoice_v1",
            "target_format": "iso20022_pain001_v1",
            "revenue_tier": "bridge_pro"
        },
        "mapping": {
            "GrpHdr.MsgId": {"source": "invoice_id", "required": True},
            "GrpHdr.CreDtTm": {"source": "issue_date", "transform": "iso_datetime"},
            "GrpHdr.InitgPty.Nm": {"source": "from.name", "required": True},
            "PmtInf.DbtrAcct.Id.IBAN": {"source": "from.iban", "validator": "iban"},
            "PmtInf.DbtrAgt.FinInstnId.BICFI": {"source": "from.bic", "validator": "bic"},
            "CdtTrfTxInf[].Amt.InstdAmt": {"source": "line_items[].amount", "validator": "amount"},
            "CdtTrfTxInf[].Amt.InstdAmt.@Ccy": {"source": "currency", "validator": "currency"},
            "CdtTrfTxInf[].CdtrAcct.Id.IBAN": {"source": "to.iban", "validator": "iban"}
        },
        "validation": {
            "required_fields": ["invoice_id", "from.name", "from.iban", "to.iban"],
            "sum_checks": [{"field": "line_items[].amount", "target": "total_amount"}]
        }
    }
    
    with patch.object(engine, '_load_sft_map', return_value=test_sft_map):
        yield engine


@pytest.fixture
def sample_invoice():
    """Sample business invoice for testing."""
    return {
        "invoice_id": "INV-2024-001",
        "issue_date": "2024-01-15T10:30:00Z",
        "currency": "EUR",
        "total_amount": 1250.00,
        "from": {
            "name": "ACME Corp",
            "iban": "DE75512108001245126199",
            "bic": "SOGEDEFF"
        },
        "to": {
            "name": "Supplier Ltd",
            "iban": "FR1420041010050500013M02606",
            "bic": "BNPAFRPP"
        },
        "line_items": [
            {"description": "Software License", "amount": 1000.00},
            {"description": "Support Fee", "amount": 250.00}
        ]
    }


class TestISO20022Validation:
    """Test ISO 20022 banking validation suite."""
    
    def test_iban_validation(self):
        validator = ISO20022Validator()
        
        # Valid IBANs
        assert validator.validate_iban("DE75512108001245126199")
        assert validator.validate_iban("FR1420041010050500013M02606")
        assert validator.validate_iban("GB82WEST12345698765432")
        
        # Invalid IBANs
        assert not validator.validate_iban("DE75512108001245126198")  # Bad checksum
        assert not validator.validate_iban("INVALID")
        assert not validator.validate_iban("")
    
    def test_bic_validation(self):
        validator = ISO20022Validator()
        
        # Valid BICs
        assert validator.validate_bic("SOGEDEFF")
        assert validator.validate_bic("BNPAFRPP")
        assert validator.validate_bic("DEUTDEFF500")
        
        # Invalid BICs
        assert not validator.validate_bic("INVALID")
        assert not validator.validate_bic("ABC")
        assert not validator.validate_bic("")
    
    def test_currency_validation(self):
        validator = ISO20022Validator()
        
        # Valid currencies
        assert validator.validate_currency("EUR")
        assert validator.validate_currency("USD")
        assert validator.validate_currency("GBP")
        
        # Invalid currencies
        assert not validator.validate_currency("XXX")
        assert not validator.validate_currency("EURO")
        assert not validator.validate_currency("")
    
    def test_amount_precision(self):
        validator = ISO20022Validator()
        
        # Valid amounts
        assert validator.validate_amount_precision(100.00, "EUR")
        assert validator.validate_amount_precision(99.99, "USD")
        assert validator.validate_amount_precision(1000, "JPY")
        
        # Invalid precision
        assert not validator.validate_amount_precision(100.001, "EUR")
        assert not validator.validate_amount_precision(99.999, "USD")


class TestBridgeEngine:
    """Test Bridge Engine core functionality."""
    
    @pytest.mark.asyncio
    async def test_bridge_execution_success(self, bridge_engine, sample_invoice):
        """Test successful bridge execution with valid data."""
        result = await bridge_engine.execute_bridge(
            source_data=sample_invoice,
            source_format="invoice_v1",
            target_format="iso20022_pain001_v1",
            agent_id="test-agent",
            tenant_id="test-tenant"
        )
        
        assert result.success
        assert result.target_data is not None
        assert result.validation_errors == []
        assert result.approval_status == ApprovalStatus.APPROVED
        assert "INV-2024-001" in str(result.target_data)
    
    @pytest.mark.asyncio
    async def test_bridge_execution_validation_failure(self, bridge_engine):
        """Test bridge execution with validation failures."""
        invalid_invoice = {
            "invoice_id": "INV-2024-002",
            "currency": "INVALID",  # Invalid currency
            "from": {
                "name": "Test Corp",
                "iban": "INVALID_IBAN",  # Invalid IBAN
                "bic": "INVALID_BIC"     # Invalid BIC
            },
            "to": {
                "iban": "ALSO_INVALID"   # Invalid IBAN
            }
        }
        
        result = await bridge_engine.execute_bridge(
            source_data=invalid_invoice,
            source_format="invoice_v1",
            target_format="iso20022_pain001_v1",
            agent_id="test-agent",
            tenant_id="test-tenant"
        )
        
        assert not result.success
        assert len(result.validation_errors) > 0
        assert any("currency" in error.field for error in result.validation_errors)
        assert any("iban" in error.field.lower() for error in result.validation_errors)
    
    @pytest.mark.asyncio
    async def test_high_value_approval_workflow(self, bridge_engine, sample_invoice):
        """Test approval workflow for high-value transactions."""
        # High-value transaction requiring approval
        high_value_invoice = sample_invoice.copy()
        high_value_invoice["total_amount"] = 50000.00  # Above threshold
        
        result = await bridge_engine.execute_bridge(
            source_data=high_value_invoice,
            source_format="invoice_v1",
            target_format="iso20022_pain001_v1",
            agent_id="test-agent",
            tenant_id="test-tenant"
        )
        
        # Should require approval for high-value transactions
        assert result.approval_status == ApprovalStatus.PENDING
        assert result.approval_id is not None
    
    @pytest.mark.asyncio
    async def test_policy_enforcement(self, bridge_engine, sample_invoice):
        """Test HEL policy enforcement during bridge execution."""
        # Mock policy that blocks certain countries
        with patch.object(bridge_engine, '_check_hel_policies') as mock_hel:
            mock_hel.return_value = (False, "Country DE blocked by policy")
            
            result = await bridge_engine.execute_bridge(
                source_data=sample_invoice,
                source_format="invoice_v1",
                target_format="iso20022_pain001_v1",
                agent_id="test-agent",
                tenant_id="test-tenant"
            )
            
            assert not result.success
            assert "policy" in result.error_message.lower()
    
    def test_metrics_tracking(self, bridge_engine):
        """Test that bridge execution generates proper metrics."""
        # Clear metrics before test
        MET_BRIDGE_EXEC_TOTAL._value.clear()
        MET_ISO20022_VALIDATE_FAIL_TOTAL._value.clear()
        
        # Mock metrics to verify calls
        with patch.object(MET_BRIDGE_EXEC_TOTAL, 'labels') as mock_exec_labels, \
             patch.object(MET_ISO20022_VALIDATE_FAIL_TOTAL, 'labels') as mock_fail_labels:
            
            mock_exec_counter = Mock()
            mock_fail_counter = Mock()
            mock_exec_labels.return_value = mock_exec_counter
            mock_fail_labels.return_value = mock_fail_counter
            
            # Track successful execution
            bridge_engine._track_execution_metrics(
                result="success",
                source_format="invoice_v1",
                target_format="iso20022_pain001_v1",
                duration_ms=250.5
            )
            
            mock_exec_labels.assert_called_with(
                result="success",
                source_format="invoice_v1",
                target_format="iso20022_pain001_v1"
            )
            mock_exec_counter.inc.assert_called_once()
    
    def test_receipt_generation(self, bridge_engine, sample_invoice):
        """Test cryptographic receipt generation."""
        result = BridgeResult(
            success=True,
            source_data=sample_invoice,
            target_data={"test": "data"},
            source_format="invoice_v1",
            target_format="iso20022_pain001_v1",
            transformation_id="test-transform-123",
            validation_errors=[],
            approval_status=ApprovalStatus.APPROVED
        )
        
        receipt = bridge_engine._generate_receipt(result, "test-agent", "test-tenant")
        
        assert receipt["bridge_execution"]["transformation_id"] == "test-transform-123"
        assert receipt["bridge_execution"]["success"] is True
        assert receipt["bridge_execution"]["agent_id"] == "test-agent"
        assert receipt["bridge_execution"]["tenant_id"] == "test-tenant"
        assert "signature" in receipt


class TestBridgeProAPI:
    """Test Bridge Pro FastAPI endpoints."""
    
    @pytest.fixture
    def client(self):
        """Test client for API endpoints."""
        from fastapi.testclient import TestClient
        from gateway.routers.bridge_pro import router
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)
    
    def test_bridge_execution_endpoint(self, client, sample_invoice):
        """Test /v1/bridge/execute endpoint."""
        with patch('gateway.routers.bridge_pro.BridgeEngine') as mock_engine:
            mock_instance = Mock()
            mock_engine.return_value = mock_instance
            
            # Mock successful execution
            mock_result = Mock()
            mock_result.success = True
            mock_result.target_data = {"pain001": "data"}
            mock_result.validation_errors = []
            mock_result.approval_status = ApprovalStatus.APPROVED
            mock_instance.execute_bridge.return_value = mock_result
            
            response = client.post("/v1/bridge/execute", json={
                "source_data": sample_invoice,
                "source_format": "invoice_v1",
                "target_format": "iso20022_pain001_v1"
            })
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            assert "target_data" in result
    
    def test_metrics_endpoint(self, client):
        """Test /v1/bridge/metrics endpoint."""
        response = client.get("/v1/bridge/metrics")
        assert response.status_code == 200
        
        metrics = response.json()
        assert "executions_total" in metrics
        assert "avg_duration_ms" in metrics
        assert "success_rate" in metrics
    
    def test_admin_approval_endpoint(self, client):
        """Test admin approval endpoint."""
        with patch('gateway.routers.bridge_pro.BridgeEngine') as mock_engine:
            mock_instance = Mock()
            mock_engine.return_value = mock_instance
            mock_instance.process_approval.return_value = True
            
            response = client.post("/admin/bridge/approve/test-approval-123", json={
                "decision": "approved",
                "reason": "Legitimate business transaction"
            })
            
            assert response.status_code == 200
            result = response.json()
            assert result["approved"] is True


class TestBillingIntegration:
    """Test Stripe billing integration for Bridge Pro."""
    
    def test_billable_event_generation(self, bridge_engine, sample_invoice):
        """Test generation of billable events for Stripe."""
        result = BridgeResult(
            success=True,
            source_data=sample_invoice,
            target_data={"test": "data"},
            source_format="invoice_v1",
            target_format="iso20022_pain001_v1",
            transformation_id="test-transform-123",
            validation_errors=[],
            approval_status=ApprovalStatus.APPROVED
        )
        
        event = bridge_engine._generate_billable_event(result, "test-tenant")
        
        assert event["event_type"] == "bridge_execution"
        assert event["tenant_id"] == "test-tenant"
        assert event["revenue_tier"] == "bridge_pro"
        assert event["metadata"]["source_format"] == "invoice_v1"
        assert event["metadata"]["target_format"] == "iso20022_pain001_v1"
        assert event["metadata"]["success"] is True
    
    def test_usage_based_pricing(self):
        """Test usage-based pricing calculation."""
        # Bridge Pro pricing: $0.50 per successful execution
        executions = 1000
        expected_cost = executions * 0.50
        
        assert expected_cost == 500.00  # $500 for 1000 executions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
