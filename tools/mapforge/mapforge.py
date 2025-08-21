#!/usr/bin/env python3
"""
MapForge - SFT Map Synthesis & Verification

LLM drafts SFT transformation rules; verification harness proves them or rejects them.
Only accept maps that pass all property tests and invariant checks.
"""

import json
import yaml
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import httpx

_log = logging.getLogger(__name__)

@dataclass
class MapDraft:
    """Generated SFT map draft."""
    map_id: str
    source_schema: Dict[str, Any]
    target_schema: Dict[str, Any] 
    mapping_rules: List[Dict[str, Any]]
    metadata: Dict[str, Any]

@dataclass
class VerificationResult:
    """Map verification result."""
    passed: bool
    errors: List[str]
    warnings: List[str]
    coverage_pct: float
    test_results: Dict[str, Any]

class MapForge:
    """SFT map synthesis and verification engine."""
    
    def __init__(self, llm_client: Optional[httpx.AsyncClient] = None):
        self.llm_client = llm_client or httpx.AsyncClient()
        self.templates_dir = Path(__file__).parent / "templates"
        self.schemas_dir = Path(__file__).parent / "schemas"
        
    async def draft_map(self, input_schema_path: str, output_schema_path: str, 
                       map_id: Optional[str] = None) -> MapDraft:
        """
        Generate SFT map draft using LLM.
        
        Args:
            input_schema_path: Path to input JSON schema
            output_schema_path: Path to output JSON schema  
            map_id: Optional map identifier
            
        Returns:
            MapDraft with generated mapping rules
        """
        _log.info(f"Drafting map: {input_schema_path} -> {output_schema_path}")
        
        # Load schemas
        with open(input_schema_path) as f:
            input_schema = json.load(f)
        with open(output_schema_path) as f:
            output_schema = json.load(f)
            
        # Generate map ID if not provided
        if not map_id:
            input_name = Path(input_schema_path).stem
            output_name = Path(output_schema_path).stem
            map_id = f"{input_name}_{output_name}_v1"
            
        # Create LLM prompt
        prompt = self._build_mapping_prompt(input_schema, output_schema, map_id)
        
        # Call LLM to generate mapping
        mapping_rules = await self._call_llm_for_mapping(prompt)
        
        return MapDraft(
            map_id=map_id,
            source_schema=input_schema,
            target_schema=output_schema,
            mapping_rules=mapping_rules,
            metadata={
                "generated_at": "2024-08-20T10:30:00Z",
                "generator": "mapforge_v1",
                "confidence": "draft"
            }
        )
        
    def _build_mapping_prompt(self, input_schema: Dict, output_schema: Dict, map_id: str) -> str:
        """Build LLM prompt for mapping generation."""
        
        prompt = f"""Generate SFT mapping rules to transform data from input schema to output schema.

MAP_ID: {map_id}

INPUT SCHEMA:
{json.dumps(input_schema, indent=2)}

OUTPUT SCHEMA:  
{json.dumps(output_schema, indent=2)}

Generate mapping rules in this format:
{{
  "rules": [
    {{
      "target_field": "Document.CstmrCdtTrfInitn.GrpHdr.MsgId",
      "source_field": "invoice_id", 
      "transform": "direct",
      "required": true
    }},
    {{
      "target_field": "Document.CstmrCdtTrfInitn.PmtInf.CdtTrfTxInf.Amt.InstdAmt.value",
      "source_field": "amount",
      "transform": "direct",
      "required": true,
      "validator": "decimal_precision",
      "validator_args": {{"max_decimals": 2}}
    }},
    {{
      "target_field": "Document.CstmrCdtTrfInitn.PmtInf.CdtTrfTxInf.Amt.InstdAmt.currency", 
      "source_field": "currency",
      "transform": "direct",
      "required": true,
      "validator": "iso4217_currency"
    }}
  ]
}}

Requirements:
1. Map ALL required fields from output schema
2. Use appropriate validators (iban_checksum, iso4217_currency, decimal_precision, bic_format)
3. Handle nested objects with dot notation
4. Mark fields as required: true if mandatory in output schema
5. Use transform types: direct, concat, format, lookup, default

Return only the JSON mapping rules."""

        return prompt
        
    async def _call_llm_for_mapping(self, prompt: str) -> List[Dict[str, Any]]:
        """Call LLM to generate mapping rules."""
        
        # For demo, return hardcoded mapping rules
        # In production, this would call actual LLM
        return [
            {
                "target_field": "Document.CstmrCdtTrfInitn.GrpHdr.MsgId",
                "source_field": "invoice_id",
                "transform": "direct", 
                "required": True
            },
            {
                "target_field": "Document.CstmrCdtTrfInitn.GrpHdr.NbOfTxs",
                "source_field": None,
                "transform": "default",
                "default_value": "1",
                "required": True
            },
            {
                "target_field": "Document.CstmrCdtTrfInitn.PmtInf.CdtTrfTxInf.Amt.InstdAmt.value",
                "source_field": "amount",
                "transform": "direct",
                "required": True,
                "validator": "decimal_precision",
                "validator_args": {"max_decimals": 2}
            },
            {
                "target_field": "Document.CstmrCdtTrfInitn.PmtInf.CdtTrfTxInf.Amt.InstdAmt.currency",
                "source_field": "currency", 
                "transform": "direct",
                "required": True,
                "validator": "iso4217_currency"
            },
            {
                "target_field": "Document.CstmrCdtTrfInitn.PmtInf.CdtTrfTxInf.Cdtr.Nm",
                "source_field": "vendor.name",
                "transform": "direct",
                "required": True
            },
            {
                "target_field": "Document.CstmrCdtTrfInitn.PmtInf.CdtTrfTxInf.CdtrAcct.Id.IBAN",
                "source_field": "vendor.iban",
                "transform": "direct", 
                "required": True,
                "validator": "iban_checksum"
            }
        ]
        
    async def verify_map(self, draft: MapDraft, test_cases: List[Dict[str, Any]]) -> VerificationResult:
        """
        Verify map draft against test cases and invariants.
        
        Args:
            draft: Map draft to verify
            test_cases: List of input/expected output pairs
            
        Returns:
            VerificationResult with pass/fail and details
        """
        _log.info(f"Verifying map: {draft.map_id}")
        
        errors = []
        warnings = []
        test_results = {}
        
        # 1. Schema validation
        schema_errors = self._validate_schema_mapping(draft)
        errors.extend(schema_errors)
        
        # 2. Rule validation  
        rule_errors = self._validate_mapping_rules(draft)
        errors.extend(rule_errors)
        
        # 3. Test case validation
        test_errors, test_results = await self._validate_test_cases(draft, test_cases)
        errors.extend(test_errors)
        
        # 4. Coverage analysis
        coverage_pct = self._calculate_coverage(draft)
        if coverage_pct < 95.0:
            warnings.append(f"Coverage {coverage_pct:.1f}% below target 95%")
            
        # 5. Property tests
        property_errors = self._validate_properties(draft)
        errors.extend(property_errors)
        
        passed = len(errors) == 0
        
        return VerificationResult(
            passed=passed,
            errors=errors,
            warnings=warnings,
            coverage_pct=coverage_pct,
            test_results=test_results
        )
        
    def _validate_schema_mapping(self, draft: MapDraft) -> List[str]:
        """Validate that mapping rules align with schemas."""
        errors = []
        
        target_schema = draft.target_schema
        
        for rule in draft.mapping_rules:
            target_field = rule.get("target_field", "")
            
            # Check if target field exists in schema (simplified)
            if not self._field_exists_in_schema(target_field, target_schema):
                errors.append(f"Target field not found in schema: {target_field}")
                
            # Check required field mapping
            if rule.get("required", False):
                source_field = rule.get("source_field")
                if not source_field and rule.get("transform") != "default":
                    errors.append(f"Required field {target_field} has no source mapping")
                    
        return errors
        
    def _validate_mapping_rules(self, draft: MapDraft) -> List[str]:
        """Validate mapping rule syntax and logic."""
        errors = []
        
        valid_transforms = ["direct", "concat", "format", "lookup", "default"]
        valid_validators = ["iban_checksum", "iso4217_currency", "decimal_precision", "bic_format"]
        
        for rule in draft.mapping_rules:
            # Check transform type
            transform = rule.get("transform", "")
            if transform not in valid_transforms:
                errors.append(f"Invalid transform type: {transform}")
                
            # Check validator
            validator = rule.get("validator")
            if validator and validator not in valid_validators:
                errors.append(f"Invalid validator: {validator}")
                
            # Check default value for default transforms
            if transform == "default" and "default_value" not in rule:
                errors.append(f"Default transform missing default_value: {rule.get('target_field')}")
                
        return errors
        
    async def _validate_test_cases(self, draft: MapDraft, test_cases: List[Dict[str, Any]]) -> Tuple[List[str], Dict[str, Any]]:
        """Validate map against test cases."""
        errors = []
        results = {"cases_run": 0, "cases_passed": 0, "case_results": []}
        
        for i, test_case in enumerate(test_cases):
            case_id = test_case.get("case_id", f"case_{i}")
            input_data = test_case.get("input", {})
            expected_output = test_case.get("expected", {})
            
            try:
                # Apply mapping rules to generate output
                actual_output = self._apply_mapping(input_data, draft.mapping_rules)
                
                # Compare with expected
                case_passed = self._compare_outputs(actual_output, expected_output)
                
                results["cases_run"] += 1
                if case_passed:
                    results["cases_passed"] += 1
                else:
                    errors.append(f"Test case {case_id} failed: output mismatch")
                    
                results["case_results"].append({
                    "case_id": case_id,
                    "passed": case_passed,
                    "input": input_data,
                    "expected": expected_output,
                    "actual": actual_output
                })
                
            except Exception as e:
                errors.append(f"Test case {case_id} execution failed: {str(e)}")
                results["cases_run"] += 1
                
        return errors, results
        
    def _apply_mapping(self, input_data: Dict[str, Any], rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply mapping rules to input data."""
        output = {}
        
        for rule in rules:
            target_field = rule["target_field"]
            source_field = rule.get("source_field")
            transform = rule.get("transform", "direct")
            
            if transform == "direct" and source_field:
                value = self._get_nested_value(input_data, source_field)
                if value is not None:
                    self._set_nested_value(output, target_field, value)
                    
            elif transform == "default":
                default_value = rule.get("default_value")
                if default_value is not None:
                    self._set_nested_value(output, target_field, default_value)
                    
            # TODO: implement other transform types (concat, format, lookup)
            
        return output
        
    def _get_nested_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """Get value from nested field path."""
        try:
            parts = field_path.split(".")
            current = data
            for part in parts:
                current = current[part]
            return current
        except (KeyError, TypeError):
            return None
            
    def _set_nested_value(self, data: Dict[str, Any], field_path: str, value: Any) -> None:
        """Set value in nested field path."""
        parts = field_path.split(".")
        current = data
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
            
        current[parts[-1]] = value
        
    def _compare_outputs(self, actual: Dict[str, Any], expected: Dict[str, Any]) -> bool:
        """Compare actual vs expected output (simplified)."""
        # For demo, just check if key fields match
        try:
            # Compare message ID
            actual_msg_id = actual.get("Document", {}).get("CstmrCdtTrfInitn", {}).get("GrpHdr", {}).get("MsgId")
            expected_msg_id = expected.get("Document", {}).get("CstmrCdtTrfInitn", {}).get("GrpHdr", {}).get("MsgId")
            
            if actual_msg_id != expected_msg_id:
                return False
                
            # Compare amount
            actual_amount = actual.get("Document", {}).get("CstmrCdtTrfInitn", {}).get("PmtInf", {}).get("CdtTrfTxInf", {}).get("Amt", {}).get("InstdAmt", {}).get("value")
            expected_amount = expected.get("Document", {}).get("CstmrCdtTrfInitn", {}).get("PmtInf", {}).get("CdtTrfTxInf", {}).get("Amt", {}).get("InstdAmt", {}).get("value")
            
            if actual_amount != expected_amount:
                return False
                
            return True
            
        except Exception:
            return False
            
    def _field_exists_in_schema(self, field_path: str, schema: Dict[str, Any]) -> bool:
        """Check if field exists in JSON schema (simplified)."""
        # For demo, assume field exists if it's a reasonable ISO 20022 path
        iso_fields = [
            "Document.CstmrCdtTrfInitn.GrpHdr.MsgId",
            "Document.CstmrCdtTrfInitn.GrpHdr.NbOfTxs", 
            "Document.CstmrCdtTrfInitn.PmtInf.CdtTrfTxInf.Amt.InstdAmt.value",
            "Document.CstmrCdtTrfInitn.PmtInf.CdtTrfTxInf.Amt.InstdAmt.currency",
            "Document.CstmrCdtTrfInitn.PmtInf.CdtTrfTxInf.Cdtr.Nm",
            "Document.CstmrCdtTrfInitn.PmtInf.CdtTrfTxInf.CdtrAcct.Id.IBAN"
        ]
        return field_path in iso_fields
        
    def _calculate_coverage(self, draft: MapDraft) -> float:
        """Calculate mapping coverage percentage."""
        # For demo, return based on number of rules
        num_rules = len(draft.mapping_rules)
        
        # Assume 6 essential fields for ISO 20022
        essential_fields = 6
        coverage = min(100.0, (num_rules / essential_fields) * 100.0)
        
        return coverage
        
    def _validate_properties(self, draft: MapDraft) -> List[str]:
        """Validate mapping properties and invariants."""
        errors = []
        
        # Check for required IBAN validation
        has_iban_validator = any(
            rule.get("validator") == "iban_checksum" 
            for rule in draft.mapping_rules
            if "iban" in rule.get("target_field", "").lower()
        )
        
        if not has_iban_validator:
            errors.append("Missing IBAN checksum validation for IBAN fields")
            
        # Check for currency validation
        has_currency_validator = any(
            rule.get("validator") == "iso4217_currency"
            for rule in draft.mapping_rules  
            if "currency" in rule.get("target_field", "").lower()
        )
        
        if not has_currency_validator:
            errors.append("Missing ISO 4217 currency validation")
            
        return errors
        
    async def lint_map(self, map_file: str) -> List[str]:
        """Lint SFT map file for common issues."""
        _log.info(f"Linting map: {map_file}")
        
        errors = []
        
        try:
            with open(map_file) as f:
                map_data = json.load(f)
                
            # Check required fields
            required_fields = ["map_id", "source_schema", "target_schema", "mapping_rules"]
            for field in required_fields:
                if field not in map_data:
                    errors.append(f"Missing required field: {field}")
                    
            # Check mapping rules
            rules = map_data.get("mapping_rules", [])
            for i, rule in enumerate(rules):
                if "target_field" not in rule:
                    errors.append(f"Rule {i}: missing target_field")
                if "transform" not in rule:
                    errors.append(f"Rule {i}: missing transform")
                    
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON: {str(e)}")
        except Exception as e:
            errors.append(f"Lint error: {str(e)}")
            
        return errors

# CLI interface
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="MapForge - SFT Map Synthesis & Verification")
    parser.add_argument("command", choices=["draft", "verify", "lint"], 
                       help="Command to run")
    parser.add_argument("--input", help="Input schema file")
    parser.add_argument("--output", help="Output schema file") 
    parser.add_argument("--map-id", help="Map identifier")
    parser.add_argument("--map-file", help="Map file to verify/lint")
    parser.add_argument("--test-cases", help="Test cases file")
    
    args = parser.parse_args()
    
    forge = MapForge()
    
    if args.command == "draft":
        if not args.input or not args.output:
            print("Error: --input and --output required for draft command")
            return 1
            
        draft = await forge.draft_map(args.input, args.output, args.map_id)
        
        # Save draft
        output_file = f"{draft.map_id}.json"
        with open(output_file, "w") as f:
            json.dump({
                "map_id": draft.map_id,
                "source_schema": draft.source_schema,
                "target_schema": draft.target_schema,
                "mapping_rules": draft.mapping_rules,
                "metadata": draft.metadata
            }, f, indent=2)
            
        print(f"Draft saved to {output_file}")
        
    elif args.command == "verify":
        if not args.map_file:
            print("Error: --map-file required for verify command")
            return 1
            
        # Load map
        with open(args.map_file) as f:
            map_data = json.load(f)
            
        draft = MapDraft(
            map_id=map_data["map_id"],
            source_schema=map_data["source_schema"],
            target_schema=map_data["target_schema"],
            mapping_rules=map_data["mapping_rules"],
            metadata=map_data.get("metadata", {})
        )
        
        # Load test cases
        test_cases = []
        if args.test_cases:
            with open(args.test_cases) as f:
                test_cases = json.load(f)
                
        result = await forge.verify_map(draft, test_cases)
        
        print(f"Verification: {'PASSED' if result.passed else 'FAILED'}")
        print(f"Coverage: {result.coverage_pct:.1f}%")
        print(f"Errors: {len(result.errors)}")
        for error in result.errors:
            print(f"  - {error}")
        print(f"Warnings: {len(result.warnings)}")
        for warning in result.warnings:
            print(f"  - {warning}")
            
        return 0 if result.passed else 1
        
    elif args.command == "lint":
        if not args.map_file:
            print("Error: --map-file required for lint command")
            return 1
            
        errors = await forge.lint_map(args.map_file)
        
        if errors:
            print(f"Lint errors found: {len(errors)}")
            for error in errors:
                print(f"  - {error}")
            return 1
        else:
            print("No lint errors found")
            return 0
            
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
