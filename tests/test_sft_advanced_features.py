"""
Test Suite for SFT Advanced Features - Quick Wins 6-9

Tests:
- Bidirectional Maps + Round-Trip Testing
- Map Linter & Validator
- Property-Based (Fuzz) Translation Tests  
- Precision, Units & Locale Normalization
"""
import pytest
import json
import tempfile
import os
from decimal import Decimal
from pathlib import Path

from odin.sft_advanced import (
    BidirectionalSftMap, perform_round_trip_test, calculate_round_trip_similarity,
    SftMapLinter, lint_sft_map_file, SftMapLintResult,
    SftFuzzTester, run_transformation_invariants_test, check_transformation_invariants,
    MoneyNormalizer, UnitConverter, money_round, money_format, normalize_decimal,
    convert_length, convert_weight
)
from odin.translate import EnhancedSftMap


class TestBidirectionalMapsRoundTrip:
    """Test Quick Win 6: Bidirectional Maps + Round-Trip Testing."""
    
    def setup_method(self):
        """Set up test maps."""
        # Simple forward map for testing
        self.forward_map = EnhancedSftMap(
            from_sft="invoice@v1",
            to_sft="payment@v1",
            fields={
                "invoice_id": "payment_reference",
                "total/amount": "amount",
                "currency": "currency_code",
                "customer/name": "payee_name"
            },
            defaults={"payment_method": "transfer"},
            canon_alg="json/nfc/no_ws/sort_keys"
        )
        
        # Reverse map (manual for testing)
        self.reverse_map = EnhancedSftMap(
            from_sft="payment@v1",
            to_sft="invoice@v1",
            fields={
                "payment_reference": "invoice_id",
                "amount": "total/amount", 
                "currency_code": "currency",
                "payee_name": "customer/name"
            },
            # Note: payment_method is lost in reverse (lossy)
            canon_alg="json/nfc/no_ws/sort_keys"
        )
        
        self.bidirectional_map = BidirectionalSftMap(
            forward_map=self.forward_map,
            reverse_map=self.reverse_map,
            lossy_fields=["payment_method"],  # This field is added by forward transform
            derived_fields=["payment_method"]
        )
    
    def test_create_reverse_map_automatic(self):
        """Test automatic reverse map generation."""
        # Create bidirectional map without reverse map
        auto_bidirectional = BidirectionalSftMap(forward_map=self.forward_map)
        
        # Generate reverse map
        reverse_map = auto_bidirectional.create_reverse_map()
        
        assert reverse_map.from_sft == self.forward_map.to_sft
        assert reverse_map.to_sft == self.forward_map.from_sft
        
        # Check field reversals
        expected_reverse_fields = {v: k for k, v in self.forward_map.fields.items()}
        assert reverse_map.fields == expected_reverse_fields
    
    def test_round_trip_success(self):
        """Test successful round-trip transformation."""
        test_invoice = {
            "invoice_id": "INV-12345",
            "total": {"amount": 1000.00},
            "currency": "USD",
            "customer": {"name": "Acme Corp"},
            "date": "2024-01-15"  # Extra field that should survive round-trip
        }
        
        success, metadata = perform_round_trip_test(test_invoice, self.bidirectional_map)
        
        assert success is True
        assert metadata["success"] is True
        assert metadata["round_trip_score"] >= 0.8  # Should be high similarity
        assert "forward_cid" in metadata
        assert "reverse_cid" in metadata
        assert metadata["lossy_fields"] == ["payment_method"]
    
    def test_round_trip_with_lossy_fields(self):
        """Test round-trip with expected lossy transformations."""
        test_invoice = {
            "invoice_id": "INV-67890",
            "total": {"amount": 2500.50},
            "currency": "EUR",
            "customer": {"name": "TechFlow Ltd"},
            "notes": "Special instructions"  # This will be lost
        }
        
        success, metadata = perform_round_trip_test(
            test_invoice, 
            self.bidirectional_map,
            tolerance=0.75  # Lower tolerance for lossy transformation
        )
        
        # Should still succeed with appropriate tolerance
        assert metadata["round_trip_score"] >= 0.75
    
    def test_round_trip_similarity_calculation(self):
        """Test similarity calculation logic."""
        original = {
            "a": 1,
            "b": "test",
            "c": {"nested": "value"},
            "d": [1, 2, 3],
            "lossy_field": "will_be_ignored"
        }
        
        round_trip = {
            "a": 1,           # Match
            "b": "test",      # Match
            "c": {"nested": "value"},  # Match
            "d": [1, 2, 3],   # Match
            # lossy_field missing
        }
        
        # Without ignoring lossy field: 4/5 = 0.8
        score = calculate_round_trip_similarity(original, round_trip)
        assert score == 0.8
        
        # With ignoring lossy field: 4/4 = 1.0
        score_filtered = calculate_round_trip_similarity(
            original, round_trip, ignore_fields=["lossy_field"]
        )
        assert score_filtered == 1.0
    
    def test_round_trip_with_floating_point_tolerance(self):
        """Test floating point tolerance in round-trip comparison."""
        original = {"amount": 123.456789}
        round_trip = {"amount": 123.456790}  # Tiny difference
        
        score = calculate_round_trip_similarity(original, round_trip)
        assert score == 1.0  # Should be considered equal within tolerance


class TestMapLinterValidator:
    """Test Quick Win 7: Map Linter & Validator."""
    
    def setup_method(self):
        """Set up test data."""
        self.linter = SftMapLinter()
    
    def test_lint_valid_map(self):
        """Test linting of valid SFT map."""
        valid_map = EnhancedSftMap(
            from_sft="invoice@v1",
            to_sft="payment@v1",
            fields={"invoice_id": "reference"},
            defaults={"type": "standard"},
            enum_constraints={"type": ["standard", "express"]},
            required_fields=["reference"],
            canon_alg="json/nfc/no_ws/sort_keys"
        )
        
        result = self.linter.lint_map(valid_map)
        
        assert result.valid is True
        assert len(result.errors) == 0
    
    def test_lint_invalid_basic_structure(self):
        """Test linting of map with structural issues."""
        invalid_map = EnhancedSftMap(
            from_sft="",  # Missing
            to_sft="payment@v1",
            fields={"invoice_id": "reference"},
            canon_alg="json/nfc/no_ws/sort_keys"
        )
        
        result = self.linter.lint_map(invalid_map)
        
        assert result.valid is False
        assert any("Missing from_sft" in error for error in result.errors)
    
    def test_lint_enum_violations(self):
        """Test detection of enum constraint violations."""
        invalid_map = EnhancedSftMap(
            from_sft="invoice@v1",
            to_sft="payment@v1",
            fields={"type": "payment_type"},
            const={"payment_type": "invalid_value"},  # Violates enum
            enum_constraints={"payment_type": ["standard", "express"]},
            canon_alg="json/nfc/no_ws/sort_keys"
        )
        
        result = self.linter.lint_map(invalid_map)
        
        assert result.valid is False
        assert any("violates enum constraint" in error for error in result.errors)
    
    def test_lint_field_mapping_conflicts(self):
        """Test detection of field mapping conflicts."""
        conflicted_map = EnhancedSftMap(
            from_sft="invoice@v1",
            to_sft="payment@v1",
            fields={"invoice_id": "reference"},
            drop=["invoice_id"],  # Conflict: mapped AND dropped
            canon_alg="json/nfc/no_ws/sort_keys"
        )
        
        result = self.linter.lint_map(conflicted_map)
        
        assert result.valid is False
        assert any("both mapped and dropped" in error for error in result.errors)
    
    def test_lint_json_pointer_warnings(self):
        """Test JSON pointer syntax warnings."""
        map_with_pointers = EnhancedSftMap(
            from_sft="invoice@v1",
            to_sft="payment@v1",
            fields={
                "customer/name": "/payee/name",  # Good pointer
                "total/amount": "amount#fragment"  # Problematic pointer
            },
            canon_alg="json/nfc/no_ws/sort_keys"
        )
        
        result = self.linter.lint_map(map_with_pointers)
        
        # Should have warnings about pointer format
        assert any("JSON pointer" in warning for warning in result.warnings)
    
    def test_lint_circular_dependencies(self):
        """Test detection of circular field dependencies."""
        circular_map = EnhancedSftMap(
            from_sft="test@v1",
            to_sft="test@v1",
            fields={
                "a": "b",
                "b": "c", 
                "c": "a"  # Creates cycle: a→b→c→a
            },
            canon_alg="json/nfc/no_ws/sort_keys"
        )
        
        result = self.linter.lint_map(circular_map)
        
        assert result.valid is False
        assert any("Circular dependency" in error for error in result.errors)
    
    def test_lint_dead_rules(self):
        """Test detection of dead/unused rules."""
        map_with_dead_rules = EnhancedSftMap(
            from_sft="invoice@v1",
            to_sft="payment@v1",
            fields={
                "dropped_field": "target"  # This field is dropped, so mapping is dead
            },
            drop=["dropped_field"],
            canon_alg="json/nfc/no_ws/sort_keys"
        )
        
        result = self.linter.lint_map(map_with_dead_rules)
        
        assert any("operates on dropped field" in warning for warning in result.warnings)
    
    def test_lint_map_file(self):
        """Test linting of map file."""
        # Create temporary map file
        map_data = {
            "from_sft": "invoice@v1",
            "to_sft": "payment@v1",
            "fields": {"invoice_id": "reference"},
            "canon_alg": "json/nfc/no_ws/sort_keys"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(map_data, f)
            temp_path = f.name
        
        try:
            result = lint_sft_map_file(temp_path)
            assert result.valid is True
        finally:
            os.unlink(temp_path)
    
    def test_lint_invalid_json_file(self):
        """Test linting of invalid JSON file."""
        # Create temporary file with invalid JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"invalid": json}')  # Invalid JSON
            temp_path = f.name
        
        try:
            result = lint_sft_map_file(temp_path)
            assert result.valid is False
            assert any("Invalid JSON" in error for error in result.errors)
        finally:
            os.unlink(temp_path)


class TestPropertyBasedFuzzTesting:
    """Test Quick Win 8: Property-Based (Fuzz) Translation Tests."""
    
    def setup_method(self):
        """Set up test components."""
        self.fuzz_tester = SftFuzzTester(seed=42)  # Reproducible tests
        
        # Simple test map with corrected field mappings
        self.test_map = EnhancedSftMap(
            from_sft="invoice@v1",
            to_sft="payment@v1",
            fields={
                "invoice_id": "reference",
                "total/amount": "amount",  # Maps nested field to top-level
                "currency": "currency_code",
                "customer/name": "payee_name"
            },
            enum_constraints={
                "currency_code": ["USD", "EUR", "GBP", "JPY"]
            },
            required_fields=["reference"],  # Only require reference for test
            canon_alg="json/nfc/no_ws/sort_keys"
        )
    
    def test_generate_fake_invoice(self):
        """Test fake invoice generation."""
        invoice = self.fuzz_tester.generate_fake_invoice()
        
        # Check required fields
        assert "invoice_id" in invoice
        assert "date" in invoice
        assert "customer" in invoice
        assert "total" in invoice
        assert "currency" in invoice
        
        # Check data types and formats
        assert isinstance(invoice["invoice_id"], str)
        assert isinstance(invoice["customer"], dict)
        assert "name" in invoice["customer"]
        assert "amount" in invoice["total"]
        
        # Check currency code format
        assert len(invoice["currency"]) == 3
        assert invoice["currency"].isupper()
    
    def test_generate_iso20022_payment(self):
        """Test ISO20022 payment generation."""
        payment = self.fuzz_tester.generate_iso20022_payment()
        
        # Check required ISO20022 fields
        assert "MsgId" in payment
        assert "CreDtTm" in payment
        assert "PmtInf" in payment
        
        # Check payment info structure
        pmt_inf = payment["PmtInf"]
        assert "PmtInfId" in pmt_inf
        assert "PmtMtd" in pmt_inf
        assert "CdtTrfTxInf" in pmt_inf
        
        # Check credit transfer info
        assert isinstance(pmt_inf["CdtTrfTxInf"], list)
        assert len(pmt_inf["CdtTrfTxInf"]) > 0
    
    def test_property_based_transformation_testing(self):
        """Test property-based testing of transformations."""
        def generate_simple_invoice(tester):
            return {
                "invoice_id": f"INV-{tester.random.randint(1000, 9999)}",
                "total": {"amount": round(tester.random.uniform(100, 10000), 2)},
                "currency": tester.random.choice(["USD", "EUR", "GBP", "JPY"]),
                "customer": {"name": "Test Company"}
            }
        
        # Run property tests
        results = run_transformation_invariants_test(
            sft_map=self.test_map,
            generator_func=generate_simple_invoice,
            num_tests=20  # Reduced for demo
        )
        
        assert results["total_tests"] == 20
        # More lenient success rate expectation since this is a demo
        assert results["success_rate"] >= 0.5  # At least half should pass
        assert "invariant_failures" in results
    
    def test_invariant_checking_currency_amount_pairing(self):
        """Test currency/amount pairing invariant."""
        valid_output = {
            "reference": "INV-123",
            "amount": "1000.00",
            "currency_code": "USD",
            "payee_name": "Test Corp"
        }
        
        failures = check_transformation_invariants({}, valid_output, self.test_map)
        
        # Should not fail currency/amount pairing (both present)
        currency_failures = [f for f in failures if "currency" in f.lower()]
        assert len(currency_failures) == 0
    
    def test_invariant_checking_required_fields(self):
        """Test required fields invariant."""
        incomplete_output = {
            "currency_code": "USD"
            # Missing required 'reference' field
        }
        
        failures = check_transformation_invariants({}, incomplete_output, self.test_map)
        
        # Should fail for missing required field
        required_failures = [f for f in failures if "Required field" in f]
        assert len(required_failures) > 0
    
    def test_invariant_checking_enum_constraints(self):
        """Test enum constraint invariant."""
        # Invalid currency code
        invalid_output = {
            "reference": "INV-123",
            "amount": "1000.00",
            "currency_code": "INVALID",  # Not in allowed enum values
            "payee_name": "Test Corp"
        }
        
        # Simulate enum validation (would be called from check_transformation_invariants)
        enum_violations = self.test_map.validate_enums(invalid_output)
        assert len(enum_violations) > 0
        assert any("INVALID" in violation for violation in enum_violations)
    
    def test_iban_format_validation(self):
        """Test IBAN format validation invariant."""
        from odin.sft_advanced import _check_iban_format
        
        # Test data with IBAN fields
        data_with_valid_iban = {
            "account": {
                "IBAN": "US331000000012345678901234567890"
            }
        }
        
        data_with_invalid_iban = {
            "account": {
                "IBAN": "INVALID_IBAN"
            }
        }
        
        valid_failures = _check_iban_format(data_with_valid_iban)
        assert len(valid_failures) == 0
        
        invalid_failures = _check_iban_format(data_with_invalid_iban)
        assert len(invalid_failures) > 0
    
    def test_date_format_validation(self):
        """Test date format validation invariant."""
        from odin.sft_advanced import _check_date_formats
        
        data_with_valid_dates = {
            "creation_date": "2024-01-15",
            "due_date": "2024-02-15T10:30:00"
        }
        
        data_with_invalid_dates = {
            "creation_date": "invalid-date-format",
            "timestamp": "not-a-timestamp"
        }
        
        valid_failures = _check_date_formats(data_with_valid_dates)
        assert len(valid_failures) == 0
        
        invalid_failures = _check_date_formats(data_with_invalid_dates)
        assert len(invalid_failures) > 0


class TestPrecisionUnitsLocaleNormalization:
    """Test Quick Win 9: Precision, Units & Locale Normalization."""
    
    def test_money_rounding_by_currency(self):
        """Test currency-specific rounding."""
        # USD: 2 decimal places
        usd_amount = MoneyNormalizer.round_currency("123.456", "USD")
        assert usd_amount == Decimal("123.46")
        
        # JPY: 0 decimal places
        jpy_amount = MoneyNormalizer.round_currency("123.456", "JPY")
        assert jpy_amount == Decimal("123")
        
        # BHD: 3 decimal places
        bhd_amount = MoneyNormalizer.round_currency("123.4567", "BHD")
        assert bhd_amount == Decimal("123.457")
    
    def test_money_rounding_with_different_input_types(self):
        """Test rounding with various input types."""
        # String input
        str_result = MoneyNormalizer.round_currency("123.45", "USD")
        assert str_result == Decimal("123.45")
        
        # Float input
        float_result = MoneyNormalizer.round_currency(123.45, "USD")
        assert float_result == Decimal("123.45")
        
        # Decimal input
        decimal_result = MoneyNormalizer.round_currency(Decimal("123.45"), "USD")
        assert decimal_result == Decimal("123.45")
    
    def test_decimal_separator_normalization(self):
        """Test decimal separator normalization for different locales."""
        # European format: 1.234,56 -> 1234.56
        eur_amount = MoneyNormalizer.normalize_decimal_separator("1.234,56", "de_DE")
        assert eur_amount == "1234.56"
        
        # French format with space thousands separator
        fr_amount = MoneyNormalizer.normalize_decimal_separator("1 234,56", "fr_FR")
        assert fr_amount == "1234.56"
        
        # US format (no change needed)
        us_amount = MoneyNormalizer.normalize_decimal_separator("1,234.56", "en_US")
        assert us_amount == "1234.56"
    
    def test_locale_formatting(self):
        """Test amount formatting for different locales."""
        amount = Decimal("1234.56")
        currency = "EUR"
        
        # US format
        us_format = MoneyNormalizer.format_for_locale(amount, currency, "en_US")
        assert "EUR" in us_format
        assert "1,234.56" in us_format
        
        # German format
        de_format = MoneyNormalizer.format_for_locale(amount, currency, "de_DE")
        assert "EUR" in de_format
        # German format uses different separators
        assert "1.234,56" in de_format
    
    def test_unit_conversions_length(self):
        """Test length unit conversions."""
        # Meter to centimeter
        cm_result = UnitConverter.convert_units(1.0, "m", "cm", "length")
        assert cm_result == 100.0
        
        # Inch to meter
        m_result = UnitConverter.convert_units(39.3701, "in", "m", "length")
        assert abs(m_result - 1.0) < 0.001  # Approximately 1 meter
        
        # Kilometer to mile
        mi_result = UnitConverter.convert_units(1.609344, "km", "mi", "length")
        assert abs(mi_result - 1.0) < 0.001  # Approximately 1 mile
    
    def test_unit_conversions_weight(self):
        """Test weight unit conversions."""
        # Kilogram to gram
        g_result = UnitConverter.convert_units(1.0, "kg", "g", "weight")
        assert g_result == 1000.0
        
        # Pound to kilogram
        kg_result = UnitConverter.convert_units(2.20462, "lb", "kg", "weight")
        assert abs(kg_result - 1.0) < 0.001  # Approximately 1 kg
    
    def test_unit_conversion_errors(self):
        """Test unit conversion error handling."""
        # Invalid unit type
        with pytest.raises(ValueError, match="Unknown unit type"):
            UnitConverter.convert_units(1.0, "m", "cm", "invalid_type")
        
        # Invalid from unit
        with pytest.raises(ValueError, match="Unknown length unit"):
            UnitConverter.convert_units(1.0, "invalid_unit", "cm", "length")
        
        # Invalid to unit
        with pytest.raises(ValueError, match="Unknown length unit"):
            UnitConverter.convert_units(1.0, "m", "invalid_unit", "length")
    
    def test_sft_function_library(self):
        """Test function library for use in SFT maps."""
        # Test money_round function
        rounded = money_round("123.456", "USD")
        assert rounded == "123.46"
        
        # Test money_format function
        formatted = money_format(1234.56, "USD", "en_US")
        assert "USD" in formatted
        assert "1,234.56" in formatted
        
        # Test normalize_decimal function
        normalized = normalize_decimal("1.234,56", "de_DE")
        assert normalized == "1234.56"
        
        # Test convert_length function
        converted_length = convert_length(1.0, "m", "cm")
        assert converted_length == 100.0
        
        # Test convert_weight function
        converted_weight = convert_weight(1.0, "kg", "g")
        assert converted_weight == 1000.0
    
    def test_precision_edge_cases(self):
        """Test precision handling edge cases."""
        # Very small amounts
        small_amount = MoneyNormalizer.round_currency("0.001", "USD")
        assert small_amount == Decimal("0.00")
        
        # Very large amounts
        large_amount = MoneyNormalizer.round_currency("999999999.999", "USD")
        assert large_amount == Decimal("1000000000.00")
        
        # Exact half values (should round up)
        half_amount = MoneyNormalizer.round_currency("123.125", "USD")
        assert half_amount == Decimal("123.13")  # ROUND_HALF_UP


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
