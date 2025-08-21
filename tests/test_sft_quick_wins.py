"""
Test suite for SFT Quick Wins implementation.

Tests the 5 quick wins:
1. Canonicalization contract (json/nfc/no_ws/sort_keys) for reproducible CIDs
2. Field-level provenance tracking in translation receipts
3. Coverage percentage and required-field gates with HEL policy integration
4. Deterministic defaults and enum validation to SFT map DSL
5. X-ODIN-SFT-Input-Type and X-ODIN-SFT-Desired-Type headers
"""
import pytest
from unittest.mock import patch
from libs.odin_core.odin.translate import (
    canonicalize_json,
    compute_canonical_cid,
    FieldProvenance,
    TranslationReceipt,
    calculate_field_coverage,
    check_required_fields,
    get_coverage_requirements,
    EnhancedSftMap,
    translate,
    extract_sft_headers,
    translate_with_headers,
    TranslateError
)


class TestCanonicalizationContract:
    """Test Quick Win 1: Canonicalization contract for reproducible CIDs."""
    
    def test_canonicalize_json_nfc_sorted(self):
        """Test json/nfc/no_ws/sort_keys canonicalization."""
        obj = {
            "intent": "test.action",
            "data": {"z_field": "café", "a_field": 42},
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        canonical = canonicalize_json(obj, "json/nfc/no_ws/sort_keys")
        expected = '{"data":{"a_field":42,"z_field":"café"},"intent":"test.action","timestamp":"2024-01-01T00:00:00Z"}'
        assert canonical == expected
    
    def test_canonicalize_json_reproducible(self):
        """Test that canonicalization is reproducible across runs."""
        obj = {"b": 2, "a": 1, "unicode": "naïve"}
        
        canon1 = canonicalize_json(obj)
        canon2 = canonicalize_json(obj)
        assert canon1 == canon2
        
        # Different input order should produce same output
        obj_reordered = {"unicode": "naïve", "a": 1, "b": 2}
        canon3 = canonicalize_json(obj_reordered)
        assert canon1 == canon3
    
    def test_compute_canonical_cid_deterministic(self):
        """Test CID computation is deterministic."""
        obj = {"action": "test", "params": {"value": 123}}
        
        cid1 = compute_canonical_cid(obj)
        cid2 = compute_canonical_cid(obj)
        assert cid1 == cid2
        assert cid1.startswith("b")  # base32 multibase prefix
    
    def test_canonicalize_unicode_normalization(self):
        """Test Unicode NFC normalization in canonicalization."""
        # é can be encoded as single char (U+00E9) or e + combining acute (U+0065 U+0301)
        obj1 = {"name": "café"}  # Single char é
        obj2 = {"name": "cafe\u0301"}  # e + combining acute
        
        canon1 = canonicalize_json(obj1)
        canon2 = canonicalize_json(obj2)
        assert canon1 == canon2  # Should normalize to same form


class TestFieldProvenanceTracking:
    """Test Quick Win 2: Field-level provenance tracking."""
    
    def test_field_provenance_creation(self):
        """Test FieldProvenance data structure."""
        fp = FieldProvenance(
            source_field="old_name",
            target_field="new_name",
            operation="rename",
            source_value="test",
            target_value="test"
        )
        assert fp.source_field == "old_name"
        assert fp.target_field == "new_name"
        assert fp.operation == "rename"
        assert isinstance(fp.timestamp, float)
    
    def test_translation_receipt_creation(self):
        """Test TranslationReceipt data structure."""
        provenance = [
            FieldProvenance("field1", "field1", "passthrough", "value1", "value1"),
            FieldProvenance("old_field", "new_field", "rename", "value2", "value2")
        ]
        
        receipt = TranslationReceipt(
            from_sft="alpha@v1",
            to_sft="beta@v1",
            input_cid="test_input_cid",
            output_cid="test_output_cid",
            field_provenance=provenance,
            coverage_percent=85.0,
            required_fields_met=True
        )
        
        assert receipt.from_sft == "alpha@v1"
        assert receipt.to_sft == "beta@v1"
        assert len(receipt.field_provenance) == 2
        assert receipt.coverage_percent == 85.0
        assert receipt.transformation_count == 0  # Gets updated during translation
    
    def test_translation_receipt_to_dict(self):
        """Test conversion of TranslationReceipt to dictionary."""
        provenance = [FieldProvenance("f1", "f1", "passthrough", "v1", "v1")]
        receipt = TranslationReceipt(
            from_sft="test@v1",
            to_sft="test@v2",
            input_cid="in_cid",
            output_cid="out_cid",
            field_provenance=provenance
        )
        
        receipt_dict = receipt.to_dict()
        assert receipt_dict["from_sft"] == "test@v1"
        assert receipt_dict["to_sft"] == "test@v2"
        assert len(receipt_dict["field_provenance"]) == 1
        assert receipt_dict["field_provenance"][0]["operation"] == "passthrough"


class TestCoverageGates:
    """Test Quick Win 3: Coverage percentage and required-field gates."""
    
    def test_calculate_field_coverage(self):
        """Test field coverage calculation."""
        input_fields = {"a", "b", "c", "d"}
        output_fields = {"a", "b", "x"}  # 2 preserved, 1 new
        
        coverage = calculate_field_coverage(input_fields, output_fields)
        assert coverage == 50.0  # 2/4 = 50%
    
    def test_calculate_field_coverage_empty_input(self):
        """Test coverage calculation with empty input."""
        coverage = calculate_field_coverage(set(), {"a", "b"})
        assert coverage == 100.0
    
    def test_check_required_fields_success(self):
        """Test required fields check when all present."""
        obj = {"name": "test", "id": 123, "status": "active"}
        required = ["name", "id"]
        
        assert check_required_fields(obj, required) is True
    
    def test_check_required_fields_missing(self):
        """Test required fields check when some missing."""
        obj = {"name": "test", "status": "active"}
        required = ["name", "id", "email"]
        
        assert check_required_fields(obj, required) is False
    
    def test_check_required_fields_null_values(self):
        """Test required fields check with null values."""
        obj = {"name": "test", "id": None, "email": ""}
        required = ["name", "id"]
        
        assert check_required_fields(obj, required) is False
    
    def test_get_coverage_requirements_defaults(self):
        """Test default coverage requirements."""
        reqs = get_coverage_requirements("unknown.sft@v1")
        assert reqs["min_coverage_percent"] == 80.0
        assert reqs["required_fields"] == []
        assert reqs["enforce_gates"] is False


class TestDeterministicDefaults:
    """Test Quick Win 4: Deterministic defaults and enum validation."""
    
    def test_enhanced_sft_map_creation(self):
        """Test EnhancedSftMap creation with defaults."""
        enhanced_map = EnhancedSftMap(
            from_sft="test@v1",
            to_sft="test@v2",
            defaults={"status": "pending", "priority": 1},
            enum_constraints={"status": ["pending", "active", "inactive"]},
            required_fields=["id", "name"]
        )
        
        assert enhanced_map.defaults["status"] == "pending"
        assert "pending" in enhanced_map.enum_constraints["status"]
        assert "id" in enhanced_map.required_fields
    
    def test_apply_defaults(self):
        """Test application of deterministic defaults."""
        enhanced_map = EnhancedSftMap(
            from_sft="test@v1",
            to_sft="test@v2",
            defaults={"status": "pending", "priority": 1}
        )
        
        obj = {"name": "test", "status": None}
        result = enhanced_map.apply_defaults(obj)
        
        assert result["name"] == "test"
        assert result["status"] == "pending"  # Applied default
        assert result["priority"] == 1  # Applied default
    
    def test_validate_enums_success(self):
        """Test enum validation with valid values."""
        enhanced_map = EnhancedSftMap(
            from_sft="test@v1",
            to_sft="test@v2",
            enum_constraints={"status": ["active", "inactive"], "type": ["user", "admin"]}
        )
        
        obj = {"status": "active", "type": "user", "name": "test"}
        violations = enhanced_map.validate_enums(obj)
        assert violations == []
    
    def test_validate_enums_violations(self):
        """Test enum validation with invalid values."""
        enhanced_map = EnhancedSftMap(
            from_sft="test@v1",
            to_sft="test@v2",
            enum_constraints={"status": ["active", "inactive"]}
        )
        
        obj = {"status": "unknown", "name": "test"}
        violations = enhanced_map.validate_enums(obj)
        assert len(violations) == 1
        assert "field_status_invalid_enum_value" in violations[0]


class TestHeaderSupport:
    """Test Quick Win 5: X-ODIN-SFT-Input-Type and X-ODIN-SFT-Desired-Type headers."""
    
    def test_extract_sft_headers(self):
        """Test extraction of SFT headers."""
        headers = {
            "X-ODIN-SFT-Input-Type": "alpha@v1",
            "X-ODIN-SFT-Desired-Type": "beta@v1",
            "X-ODIN-SFT-Canon-Alg": "json/sort_keys",
            "Content-Type": "application/json",
            "Authorization": "Bearer token"
        }
        
        sft_headers = extract_sft_headers(headers)
        assert sft_headers["input_type"] == "alpha@v1"
        assert sft_headers["desired_type"] == "beta@v1"
        assert sft_headers["canon_alg"] == "json/sort_keys"
        assert "content-type" not in sft_headers  # Not SFT header
    
    def test_extract_sft_headers_case_insensitive(self):
        """Test case-insensitive header extraction."""
        headers = {
            "x-odin-sft-input-type": "test@v1",
            "X-Odin-Sft-Desired-Type": "test@v2"
        }
        
        sft_headers = extract_sft_headers(headers)
        assert sft_headers["input_type"] == "test@v1"
        assert sft_headers["desired_type"] == "test@v2"
    
    @patch('libs.odin_core.odin.translate.resolve_map_path')
    @patch('libs.odin_core.odin.translate.load_map_from_path')
    def test_translate_with_headers_success(self, mock_load_map, mock_resolve_path):
        """Test translation using headers."""
        # Mock the map loading
        mock_resolve_path.return_value = "/path/to/map.json"
        mock_load_map.return_value = EnhancedSftMap(
            from_sft="alpha@v1",
            to_sft="beta@v1",
            fields={"old_name": "new_name"}
        )
        
        payload = {"old_name": "test_value", "id": 123}
        headers = {
            "X-ODIN-SFT-Input-Type": "alpha@v1",
            "X-ODIN-SFT-Desired-Type": "beta@v1"
        }
        
        # Mock the validate_obj to always pass
        with patch('libs.odin_core.odin.translate.validate_obj', return_value=[]):
            result, receipt = translate_with_headers(payload, headers)
            
            assert "new_name" in result
            assert result["new_name"] == "test_value"
            assert receipt.from_sft == "alpha@v1"
            assert receipt.to_sft == "beta@v1"
    
    def test_translate_with_headers_missing_headers(self):
        """Test translation with missing required headers."""
        payload = {"test": "value"}
        headers = {"X-ODIN-SFT-Input-Type": "alpha@v1"}  # Missing desired type
        
        with pytest.raises(TranslateError) as exc_info:
            translate_with_headers(payload, headers)
        
        assert exc_info.value.code == "odin.translate.missing_type_headers"


class TestIntegratedTranslation:
    """Test integrated translation with all Quick Win features."""
    
    def test_translate_with_enhanced_map_and_receipt(self):
        """Test full translation with enhanced features."""
        enhanced_map = EnhancedSftMap(
            from_sft="test@v1",
            to_sft="test@v2",
            fields={"old_field": "new_field"},
            const={"version": "2.0"},
            drop=["deprecated_field"],
            defaults={"status": "active"}
        )
        
        payload = {
            "old_field": "test_value",
            "deprecated_field": "remove_me",
            "keep_field": "unchanged"
        }
        
        # Mock validation to always pass
        with patch('libs.odin_core.odin.translate.validate_obj', return_value=[]):
            result, receipt = translate(payload, enhanced_map, generate_receipt=True)
            
            # Check transformation results
            assert "new_field" in result
            assert result["new_field"] == "test_value"
            assert "deprecated_field" not in result
            assert result["keep_field"] == "unchanged"
            assert result["version"] == "2.0"
            assert result["status"] == "active"
            
            # Check receipt details
            assert receipt.from_sft == "test@v1"
            assert receipt.to_sft == "test@v2"
            assert len(receipt.field_provenance) > 0
            assert receipt.coverage_percent >= 0
            
            # Check provenance tracking
            operations = [fp.operation for fp in receipt.field_provenance]
            assert "default" in operations  # status default
            assert "drop" in operations  # deprecated_field
            assert "rename" in operations  # old_field -> new_field
            assert "const" in operations  # version
            assert "passthrough" in operations  # keep_field
    
    def test_translate_coverage_gate_enforcement(self):
        """Test coverage gate enforcement."""
        enhanced_map = EnhancedSftMap(
            from_sft="test@v1",
            to_sft="test@v2",
            drop=["field1", "field2", "field3"]  # Drop most fields
        )
        
        payload = {"field1": "a", "field2": "b", "field3": "c", "field4": "d"}
        
        # Mock coverage requirements to enforce gates
        with patch('libs.odin_core.odin.translate.get_coverage_requirements') as mock_reqs:
            mock_reqs.return_value = {
                "min_coverage_percent": 75.0,
                "required_fields": [],
                "enforce_gates": True
            }
            
            with patch('libs.odin_core.odin.translate.validate_obj', return_value=[]):
                with pytest.raises(TranslateError) as exc_info:
                    translate(payload, enhanced_map)
                
                assert exc_info.value.code == "odin.translate.insufficient_coverage"
                assert exc_info.value.coverage_percent is not None
    
    def test_translate_enum_constraint_violation(self):
        """Test enum constraint enforcement."""
        enhanced_map = EnhancedSftMap(
            from_sft="test@v1",
            to_sft="test@v2",
            enum_constraints={"status": ["active", "inactive"]},
            const={"status": "unknown"}  # Invalid enum value
        )
        
        payload = {"name": "test"}
        
        with patch('libs.odin_core.odin.translate.validate_obj', return_value=[]):
            with pytest.raises(TranslateError) as exc_info:
                translate(payload, enhanced_map)
            
            assert exc_info.value.code == "odin.translate.enum_violation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
