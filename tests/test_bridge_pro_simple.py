"""
Simple Bridge Pro demonstration test.
"""
import asyncio
import pytest
from libs.odin_core.odin.bridge_engine import BridgeEngine, ApprovalStatus


@pytest.mark.asyncio
async def test_bridge_pro_basic_functionality():
    """Test basic Bridge Pro functionality."""
    # Create bridge engine
    engine = BridgeEngine()
    
    # Sample invoice data
    invoice_data = {
        "invoice_id": "INV-2024-001",
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
        }
    }
    
    # Execute bridge transformation
    result = await engine.execute_bridge(
        source_data=invoice_data,
        source_format="invoice_v1",
        target_format="iso20022_pain001_v1",
        agent_id="test-agent",
        tenant_id="test-tenant"
    )
    
    # Basic assertions
    assert result is not None
    assert result.transformation_id is not None
    assert result.source_format == "invoice_v1"
    assert result.target_format == "iso20022_pain001_v1"
    assert result.execution_time_ms > 0
    
    print(f"Bridge Pro execution successful!")
    print(f"Transformation ID: {result.transformation_id}")
    print(f"Success: {result.success}")
    print(f"Approval Status: {result.approval_status}")
    print(f"Execution Time: {result.execution_time_ms:.2f}ms")
    
    if result.target_data:
        print(f"Target data generated: {len(str(result.target_data))} chars")


@pytest.mark.asyncio  
async def test_high_value_approval_workflow():
    """Test approval workflow for high-value transactions."""
    engine = BridgeEngine()
    
    # High-value transaction
    high_value_data = {
        "invoice_id": "INV-2024-002",
        "currency": "USD",
        "total_amount": 50000.00,  # Above $10k threshold
        "from": {"name": "BigCorp", "iban": "US1234567890"},
        "to": {"name": "Vendor", "iban": "US0987654321"}
    }
    
    result = await engine.execute_bridge(
        source_data=high_value_data,
        source_format="invoice_v1", 
        target_format="iso20022_pain001_v1",
        agent_id="test-agent",
        tenant_id="test-tenant"
    )
    
    # Should require approval for high-value
    assert result.approval_status == ApprovalStatus.PENDING
    assert result.approval_id is not None
    
    print(f"High-value transaction requires approval: {result.approval_id}")


def test_iso20022_validation_functions():
    """Test ISO 20022 validation functions."""
    from libs.odin_core.odin.validators.iso20022 import (
        validate_iban, validate_bic, validate_currency
    )
    
    # Test IBAN validation
    iban_result = validate_iban("DE75512108001245126199")
    assert iban_result["valid"] is True
    
    # Test BIC validation  
    bic_result = validate_bic("SOGEDEFF")
    assert bic_result["valid"] is True
    
    # Test currency validation
    currency_result = validate_currency("EUR")
    assert currency_result["valid"] is True
    
    print("ISO 20022 validation functions working correctly!")


if __name__ == "__main__":
    asyncio.run(test_bridge_pro_basic_functionality())
    asyncio.run(test_high_value_approval_workflow())
    test_iso20022_validation_functions()
    print("All Bridge Pro tests passed!")
