"""
SFT Advanced Features Implementation - Quick Wins 6-9

6. Bidirectional Maps + Round-Trip Testing
7. Map Linter & Validator  
8. Property-Based (Fuzz) Translation Tests
9. Precision, Units & Locale Normalization
"""
import json
import re
from typing import Dict, Any, List, Optional, Tuple, Union
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
import locale
from pathlib import Path

from .translate import EnhancedSftMap, translate, TranslateError, TranslationReceipt


# ========== QUICK WIN 6: BIDIRECTIONAL MAPS + ROUND-TRIP TESTING ==========

@dataclass
class BidirectionalSftMap:
    """Enhanced SFT map with reverse mapping support for round-trip testing."""
    forward_map: EnhancedSftMap
    reverse_map: Optional[EnhancedSftMap] = None
    lossy_fields: List[str] = field(default_factory=list)  # Fields expected to be lost
    derived_fields: List[str] = field(default_factory=list)  # Fields added by transformation
    
    def create_reverse_map(self) -> EnhancedSftMap:
        """Generate reverse map from forward map (best effort)."""
        if self.reverse_map:
            return self.reverse_map
            
        # Reverse field mappings
        reverse_fields = {v: k for k, v in self.forward_map.fields.items()}
        
        # Reverse intent mappings
        reverse_intents = {v: k for k, v in self.forward_map.intents.items()}
        
        # Create reverse map (approximate - may need manual adjustment)
        self.reverse_map = EnhancedSftMap(
            from_sft=self.forward_map.to_sft,
            to_sft=self.forward_map.from_sft,
            fields=reverse_fields,
            intents=reverse_intents,
            # Note: const fields and drops are harder to reverse automatically
            canon_alg=self.forward_map.canon_alg
        )
        
        return self.reverse_map


def perform_round_trip_test(
    payload: Dict[str, Any], 
    bidirectional_map: BidirectionalSftMap,
    tolerance: float = 0.95
) -> Tuple[bool, Dict[str, Any]]:
    """
    Perform round-trip test: input → forward_map → reverse_map ≈ input
    
    Args:
        payload: Original input
        bidirectional_map: Forward and reverse maps
        tolerance: Similarity threshold for round-trip success
        
    Returns:
        (success, metadata) tuple with round-trip results
    """
    try:
        # Forward transformation
        forward_result, forward_receipt = translate(
            payload, bidirectional_map.forward_map, generate_receipt=True
        )
        
        # Reverse transformation
        reverse_map = bidirectional_map.create_reverse_map()
        reverse_result, reverse_receipt = translate(
            forward_result, reverse_map, generate_receipt=True
        )
        
        # Compare original vs round-trip result
        round_trip_score = calculate_round_trip_similarity(
            payload, reverse_result, 
            ignore_fields=bidirectional_map.lossy_fields + bidirectional_map.derived_fields
        )
        
        success = round_trip_score >= tolerance
        
        metadata = {
            "round_trip_score": round_trip_score,
            "tolerance": tolerance,
            "success": success,
            "forward_coverage": forward_receipt.coverage_percent,
            "reverse_coverage": reverse_receipt.coverage_percent,
            "lossy_fields": bidirectional_map.lossy_fields,
            "derived_fields": bidirectional_map.derived_fields,
            "forward_cid": forward_receipt.output_cid,
            "reverse_cid": reverse_receipt.output_cid
        }
        
        return success, metadata
        
    except Exception as e:
        return False, {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


def calculate_round_trip_similarity(
    original: Dict[str, Any], 
    round_trip: Dict[str, Any],
    ignore_fields: List[str] = None
) -> float:
    """Calculate similarity score between original and round-trip result."""
    ignore_fields = ignore_fields or []
    
    # Filter out ignored fields
    orig_filtered = {k: v for k, v in original.items() if k not in ignore_fields}
    rt_filtered = {k: v for k, v in round_trip.items() if k not in ignore_fields}
    
    if not orig_filtered:
        return 1.0  # Empty comparison is perfect match
    
    # Count matching fields
    matches = 0
    total = len(orig_filtered)
    
    for key, orig_value in orig_filtered.items():
        if key in rt_filtered:
            rt_value = rt_filtered[key]
            if _values_equal(orig_value, rt_value):
                matches += 1
    
    return matches / total if total > 0 else 1.0


def _values_equal(v1: Any, v2: Any, tolerance: float = 1e-6) -> bool:
    """Compare values with tolerance for floating point numbers."""
    if type(v1) != type(v2):
        return False
    
    if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
        return abs(float(v1) - float(v2)) < tolerance
    
    if isinstance(v1, dict) and isinstance(v2, dict):
        if set(v1.keys()) != set(v2.keys()):
            return False
        return all(_values_equal(v1[k], v2[k]) for k in v1.keys())
    
    if isinstance(v1, list) and isinstance(v2, list):
        if len(v1) != len(v2):
            return False
        return all(_values_equal(v1[i], v2[i]) for i in range(len(v1)))
    
    return v1 == v2


# ========== QUICK WIN 7: MAP LINTER & VALIDATOR ==========

@dataclass
class SftMapLintResult:
    """Results from SFT map linting/validation."""
    valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


class SftMapLinter:
    """Linter and validator for SFT maps."""
    
    def lint_map(self, sft_map: Union[EnhancedSftMap, Dict[str, Any]]) -> SftMapLintResult:
        """Comprehensive linting of SFT map."""
        result = SftMapLintResult()
        
        # Convert dict to map if needed
        if isinstance(sft_map, dict):
            try:
                sft_map = self._dict_to_enhanced_map(sft_map)
            except Exception as e:
                result.valid = False
                result.errors.append(f"Invalid map structure: {e}")
                return result
        
        # Run all lint checks
        self._lint_basic_structure(sft_map, result)
        self._lint_field_mappings(sft_map, result)
        self._lint_enum_constraints(sft_map, result)
        self._lint_defaults(sft_map, result)
        self._lint_json_pointers(sft_map, result)
        self._lint_circular_dependencies(sft_map, result)
        self._lint_dead_rules(sft_map, result)
        
        return result
    
    def _dict_to_enhanced_map(self, data: Dict[str, Any]) -> EnhancedSftMap:
        """Convert dictionary to EnhancedSftMap."""
        return EnhancedSftMap(
            from_sft=data.get("from_sft", ""),
            to_sft=data.get("to_sft", ""),
            fields=data.get("fields", {}),
            intents=data.get("intents", {}),
            const=data.get("const", {}),
            drop=data.get("drop", []),
            defaults=data.get("defaults", {}),
            enum_constraints=data.get("enum_constraints", {}),
            required_fields=data.get("required_fields", []),
            canon_alg=data.get("canon_alg", "json/nfc/no_ws/sort_keys")
        )
    
    def _lint_basic_structure(self, sft_map: EnhancedSftMap, result: SftMapLintResult):
        """Validate basic map structure."""
        if not sft_map.from_sft:
            result.errors.append("Missing from_sft specification")
            result.valid = False
        
        if not sft_map.to_sft:
            result.errors.append("Missing to_sft specification")
            result.valid = False
        
        if sft_map.from_sft == sft_map.to_sft:
            result.warnings.append("from_sft and to_sft are identical (identity transform)")
        
        # Validate SFT naming convention
        sft_pattern = r'^[a-zA-Z0-9_.-]+@v\d+$'
        if sft_map.from_sft and not re.match(sft_pattern, sft_map.from_sft):
            result.warnings.append(f"from_sft '{sft_map.from_sft}' doesn't follow convention (name@v1)")
        
        if sft_map.to_sft and not re.match(sft_pattern, sft_map.to_sft):
            result.warnings.append(f"to_sft '{sft_map.to_sft}' doesn't follow convention (name@v1)")
    
    def _lint_field_mappings(self, sft_map: EnhancedSftMap, result: SftMapLintResult):
        """Validate field mappings."""
        for source, target in sft_map.fields.items():
            if not isinstance(source, str) or not isinstance(target, str):
                result.errors.append(f"Field mapping must be string→string: {source}→{target}")
                result.valid = False
            
            if source == target:
                result.warnings.append(f"Redundant field mapping: {source}→{target}")
            
            # Check for conflicts with drop list
            if source in sft_map.drop:
                result.errors.append(f"Field '{source}' is both mapped and dropped")
                result.valid = False
    
    def _lint_enum_constraints(self, sft_map: EnhancedSftMap, result: SftMapLintResult):
        """Validate enum constraints."""
        for field, allowed_values in sft_map.enum_constraints.items():
            if not isinstance(allowed_values, list):
                result.errors.append(f"Enum constraint for '{field}' must be a list")
                result.valid = False
                continue
            
            if len(allowed_values) == 0:
                result.warnings.append(f"Empty enum constraint for field '{field}'")
            
            if len(set(allowed_values)) != len(allowed_values):
                result.warnings.append(f"Duplicate values in enum constraint for '{field}'")
            
            # Check if const values satisfy enum constraints
            if field in sft_map.const:
                const_value = sft_map.const[field]
                if const_value not in allowed_values:
                    result.errors.append(
                        f"Const value '{const_value}' for field '{field}' violates enum constraint {allowed_values}"
                    )
                    result.valid = False
    
    def _lint_defaults(self, sft_map: EnhancedSftMap, result: SftMapLintResult):
        """Validate default values."""
        for field, default_value in sft_map.defaults.items():
            # Check for conflicts with const
            if field in sft_map.const:
                result.warnings.append(f"Field '{field}' has both default and const values (const wins)")
            
            # Check against enum constraints
            if field in sft_map.enum_constraints:
                allowed_values = sft_map.enum_constraints[field]
                if default_value not in allowed_values:
                    result.errors.append(
                        f"Default value '{default_value}' for field '{field}' violates enum constraint {allowed_values}"
                    )
                    result.valid = False
    
    def _lint_json_pointers(self, sft_map: EnhancedSftMap, result: SftMapLintResult):
        """Validate JSON pointer syntax in field paths."""
        all_paths = list(sft_map.fields.keys()) + list(sft_map.fields.values())
        
        for path in all_paths:
            if '/' in path:
                # Basic JSON pointer validation
                if not path.startswith('/'):
                    result.warnings.append(f"JSON pointer '{path}' should start with '/'")
                
                # Check for invalid characters
                if any(char in path for char in ['#', '?', '[', ']']):
                    result.warnings.append(f"JSON pointer '{path}' contains potentially problematic characters")
    
    def _lint_circular_dependencies(self, sft_map: EnhancedSftMap, result: SftMapLintResult):
        """Check for circular field dependencies."""
        # Build dependency graph
        dependencies = {}
        for source, target in sft_map.fields.items():
            dependencies[target] = source
        
        # Simple cycle detection
        visited = set()
        for field in dependencies:
            if field in visited:
                continue
                
            path = []
            current = field
            while current in dependencies and current not in visited:
                if current in path:
                    result.errors.append(f"Circular dependency detected: {' → '.join(path + [current])}")
                    result.valid = False
                    break
                path.append(current)
                current = dependencies[current]
            
            visited.update(path)
    
    def _lint_dead_rules(self, sft_map: EnhancedSftMap, result: SftMapLintResult):
        """Identify potentially dead/unused rules."""
        # Fields that will be dropped before processing
        early_drops = set(sft_map.drop)
        
        # Field mappings that source from dropped fields
        for source, target in sft_map.fields.items():
            if source in early_drops:
                result.warnings.append(f"Field mapping '{source}→{target}' operates on dropped field")


def lint_sft_map_file(map_path: str) -> SftMapLintResult:
    """Lint an SFT map file."""
    linter = SftMapLinter()
    
    try:
        with open(map_path, 'r', encoding='utf-8') as f:
            map_data = json.load(f)
        
        return linter.lint_map(map_data)
        
    except FileNotFoundError:
        result = SftMapLintResult(valid=False)
        result.errors.append(f"Map file not found: {map_path}")
        return result
    except json.JSONDecodeError as e:
        result = SftMapLintResult(valid=False)
        result.errors.append(f"Invalid JSON in map file: {e}")
        return result
    except Exception as e:
        result = SftMapLintResult(valid=False)
        result.errors.append(f"Error reading map file: {e}")
        return result


# ========== QUICK WIN 8: PROPERTY-BASED (FUZZ) TRANSLATION TESTS ==========

import random
import string
from datetime import datetime, timedelta


class SftFuzzTester:
    """Property-based testing for SFT transformations."""
    
    def __init__(self, seed: int = 42):
        """Initialize with reproducible random seed."""
        self.random = random.Random(seed)
    
    def generate_fake_invoice(self) -> Dict[str, Any]:
        """Generate realistic fake invoice data for testing."""
        return {
            "invoice_id": self._generate_invoice_id(),
            "date": self._generate_date(),
            "due_date": self._generate_due_date(),
            "customer": self._generate_customer(),
            "items": self._generate_line_items(),
            "total": self._generate_monetary_amount(),
            "currency": self._generate_currency(),
            "payment_terms": self._generate_payment_terms(),
            "notes": self._generate_notes()
        }
    
    def generate_iso20022_payment(self) -> Dict[str, Any]:
        """Generate realistic ISO20022 payment instruction."""
        return {
            "MsgId": self._generate_message_id(),
            "CreDtTm": self._generate_iso_datetime(),
            "NbOfTxs": str(self.random.randint(1, 100)),
            "CtrlSum": self._generate_decimal_amount(),
            "PmtInf": {
                "PmtInfId": self._generate_payment_info_id(),
                "PmtMtd": "TRF",
                "ReqdExctnDt": self._generate_iso_date(),
                "Dbtr": self._generate_debtor(),
                "DbtrAcct": self._generate_account(),
                "DbtrAgt": self._generate_bic(),
                "CdtTrfTxInf": self._generate_credit_transfer_info()
            }
        }
    
    def _generate_invoice_id(self) -> str:
        """Generate realistic invoice ID."""
        prefixes = ["INV", "BILL", "RCP", "DOC"]
        prefix = self.random.choice(prefixes)
        number = self.random.randint(100000, 999999)
        return f"{prefix}-{number}"
    
    def _generate_date(self) -> str:
        """Generate random date in ISO format."""
        start = datetime(2023, 1, 1)
        end = datetime(2024, 12, 31)
        delta = end - start
        random_days = self.random.randint(0, delta.days)
        random_date = start + timedelta(days=random_days)
        return random_date.strftime("%Y-%m-%d")
    
    def _generate_due_date(self) -> str:
        """Generate due date (future)."""
        start = datetime.now()
        end = start + timedelta(days=90)
        delta = end - start
        random_days = self.random.randint(0, delta.days)
        random_date = start + timedelta(days=random_days)
        return random_date.strftime("%Y-%m-%d")
    
    def _generate_customer(self) -> Dict[str, Any]:
        """Generate customer information."""
        companies = ["Acme Corp", "TechFlow Ltd", "Global Systems", "Metro Dynamics"]
        return {
            "name": self.random.choice(companies),
            "address": self._generate_address(),
            "tax_id": self._generate_tax_id(),
            "contact_email": self._generate_email()
        }
    
    def _generate_address(self) -> Dict[str, str]:
        """Generate address."""
        streets = ["Main St", "Oak Ave", "Business Blvd", "Commerce Way"]
        cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"]
        states = ["NY", "CA", "IL", "TX", "AZ"]
        
        return {
            "street": f"{self.random.randint(100, 9999)} {self.random.choice(streets)}",
            "city": self.random.choice(cities),
            "state": self.random.choice(states),
            "zip": f"{self.random.randint(10000, 99999)}"
        }
    
    def _generate_line_items(self) -> List[Dict[str, Any]]:
        """Generate invoice line items."""
        items = []
        num_items = self.random.randint(1, 5)
        
        products = ["Software License", "Consulting Services", "Hardware", "Support Plan"]
        
        for _ in range(num_items):
            quantity = self.random.randint(1, 100)
            unit_price = round(self.random.uniform(10.00, 1000.00), 2)
            
            items.append({
                "description": self.random.choice(products),
                "quantity": quantity,
                "unit_price": unit_price,
                "total": round(quantity * unit_price, 2)
            })
        
        return items
    
    def _generate_monetary_amount(self) -> Dict[str, Any]:
        """Generate monetary amount with proper precision."""
        amount = round(self.random.uniform(100.00, 50000.00), 2)
        return {
            "amount": amount,
            "formatted": f"{amount:.2f}"
        }
    
    def _generate_currency(self) -> str:
        """Generate currency code."""
        currencies = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD"]
        return self.random.choice(currencies)
    
    def _generate_payment_terms(self) -> str:
        """Generate payment terms."""
        terms = ["Net 30", "Net 15", "Due on Receipt", "2/10 Net 30"]
        return self.random.choice(terms)
    
    def _generate_notes(self) -> str:
        """Generate invoice notes."""
        notes = [
            "Thank you for your business!",
            "Payment due within terms specified.",
            "Contact us with any questions.",
            "Late fees may apply after due date."
        ]
        return self.random.choice(notes)
    
    def _generate_message_id(self) -> str:
        """Generate ISO20022 message ID."""
        return f"MSG{datetime.now().strftime('%Y%m%d')}{self.random.randint(1000, 9999)}"
    
    def _generate_iso_datetime(self) -> str:
        """Generate ISO20022 datetime."""
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    def _generate_iso_date(self) -> str:
        """Generate ISO20022 date."""
        return datetime.now().strftime("%Y-%m-%d")
    
    def _generate_decimal_amount(self) -> str:
        """Generate decimal amount as string."""
        amount = round(self.random.uniform(100.00, 100000.00), 2)
        return f"{amount:.2f}"
    
    def _generate_payment_info_id(self) -> str:
        """Generate payment info ID."""
        return f"PMT{self.random.randint(100000, 999999)}"
    
    def _generate_debtor(self) -> Dict[str, str]:
        """Generate debtor information."""
        return {
            "Nm": "Test Company Ltd",
            "PstlAdr": {
                "Ctry": "US",
                "AdrLine": ["123 Business St", "Suite 100"]
            }
        }
    
    def _generate_account(self) -> Dict[str, str]:
        """Generate account information."""
        return {
            "Id": {
                "IBAN": self._generate_iban()
            }
        }
    
    def _generate_iban(self) -> str:
        """Generate valid-format IBAN (US format)."""
        # Simplified US IBAN generation for testing
        bank_code = "".join(self.random.choices(string.digits, k=8))
        account_number = "".join(self.random.choices(string.digits, k=10))
        return f"US{self.random.randint(10, 99)}{bank_code}{account_number}"
    
    def _generate_bic(self) -> Dict[str, str]:
        """Generate BIC code."""
        bank_codes = ["CHASUS33", "BOFAUS3N", "CITIUS33", "WFBIUS6S"]
        return {
            "FinInstnId": {
                "BIC": self.random.choice(bank_codes)
            }
        }
    
    def _generate_credit_transfer_info(self) -> List[Dict[str, Any]]:
        """Generate credit transfer information."""
        return [{
            "PmtId": {
                "InstrId": f"INSTR{self.random.randint(100000, 999999)}",
                "EndToEndId": f"E2E{self.random.randint(100000, 999999)}"
            },
            "Amt": {
                "InstdAmt": {
                    "#text": self._generate_decimal_amount(),
                    "@Ccy": self._generate_currency()
                }
            },
            "Cdtr": {
                "Nm": "Beneficiary Company"
            },
            "CdtrAcct": {
                "Id": {
                    "IBAN": self._generate_iban()
                }
            }
        }]
    
    def _generate_tax_id(self) -> str:
        """Generate tax ID."""
        return f"{self.random.randint(10, 99)}-{self.random.randint(1000000, 9999999)}"
    
    def _generate_email(self) -> str:
        """Generate email address."""
        domains = ["company.com", "business.org", "corp.net"]
        name = "".join(self.random.choices(string.ascii_lowercase, k=8))
        domain = self.random.choice(domains)
        return f"{name}@{domain}"


def run_transformation_invariants_test(
    sft_map: EnhancedSftMap,
    generator_func: callable,
    num_tests: int = 100
) -> Dict[str, Any]:
    """Run property-based tests on SFT transformation."""
    fuzz_tester = SftFuzzTester()
    invariant_failures = []
    successful_tests = 0
    
    for i in range(num_tests):
        try:
            # Generate test data
            test_input = generator_func(fuzz_tester)
            
            # Perform transformation
            result, receipt = translate(test_input, sft_map, generate_receipt=True)
            
            # Test invariants
            failures = check_transformation_invariants(test_input, result, sft_map)
            
            if failures:
                invariant_failures.extend([
                    {
                        "test_case": i,
                        "input": test_input,
                        "output": result,
                        "failures": failures
                    }
                ])
            else:
                successful_tests += 1
                
        except Exception as e:
            invariant_failures.append({
                "test_case": i,
                "error": str(e),
                "error_type": type(e).__name__
            })
    
    return {
        "total_tests": num_tests,
        "successful_tests": successful_tests,
        "failed_tests": len(invariant_failures),
        "success_rate": successful_tests / num_tests,
        "invariant_failures": invariant_failures[:10]  # Limit to first 10 failures
    }


def check_transformation_invariants(
    input_data: Dict[str, Any],
    output_data: Dict[str, Any],
    sft_map: EnhancedSftMap
) -> List[str]:
    """Check transformation invariants."""
    failures = []
    
    # Invariant 1: Amount/currency pairing preservation
    failures.extend(_check_currency_amount_pairing(input_data, output_data))
    
    # Invariant 2: IBAN length validation
    failures.extend(_check_iban_format(output_data))
    
    # Invariant 3: Date format consistency
    failures.extend(_check_date_formats(output_data))
    
    # Invariant 4: Required fields present
    if sft_map.required_fields:
        for field in sft_map.required_fields:
            if field not in output_data or output_data[field] is None:
                failures.append(f"Required field '{field}' missing or null in output")
    
    # Invariant 5: Enum constraints satisfied
    enum_violations = sft_map.validate_enums(output_data)
    failures.extend(enum_violations)
    
    return failures


def _check_currency_amount_pairing(input_data: Dict[str, Any], output_data: Dict[str, Any]) -> List[str]:
    """Check that currency and amount fields are properly paired."""
    failures = []
    
    # Look for amount/currency patterns in output
    amount_fields = [k for k in output_data.keys() if 'amount' in k.lower()]
    currency_fields = [k for k in output_data.keys() if 'currency' in k.lower() or 'ccy' in k.lower()]
    
    for amount_field in amount_fields:
        if not any(curr_field for curr_field in currency_fields):
            failures.append(f"Amount field '{amount_field}' has no corresponding currency field")
    
    return failures


def _check_iban_format(data: Dict[str, Any]) -> List[str]:
    """Check IBAN format in nested data."""
    failures = []
    
    def check_iban_recursive(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                if key.upper() == "IBAN" and isinstance(value, str):
                    if not _is_valid_iban_format(value):
                        failures.append(f"Invalid IBAN format at {new_path}: {value}")
                else:
                    check_iban_recursive(value, new_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                check_iban_recursive(item, f"{path}[{i}]")
    
    check_iban_recursive(data)
    return failures


def _is_valid_iban_format(iban: str) -> bool:
    """Basic IBAN format validation."""
    if not isinstance(iban, str):
        return False
    
    # Remove spaces and convert to uppercase
    iban = iban.replace(" ", "").upper()
    
    # Basic format: 2 letters + 2 digits + up to 30 alphanumeric
    if len(iban) < 15 or len(iban) > 34:
        return False
    
    if not re.match(r'^[A-Z]{2}[0-9]{2}[A-Z0-9]+$', iban):
        return False
    
    return True


def _check_date_formats(data: Dict[str, Any]) -> List[str]:
    """Check date format consistency."""
    failures = []
    
    def check_dates_recursive(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                if any(date_word in key.lower() for date_word in ['date', 'dt', 'time']):
                    if isinstance(value, str) and not _is_valid_date_format(value):
                        failures.append(f"Invalid date format at {new_path}: {value}")
                else:
                    check_dates_recursive(value, new_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                check_dates_recursive(item, f"{path}[{i}]")
    
    check_dates_recursive(data)
    return failures


def _is_valid_date_format(date_str: str) -> bool:
    """Validate common date formats."""
    formats = [
        "%Y-%m-%d",           # 2024-01-01
        "%Y-%m-%dT%H:%M:%S",  # 2024-01-01T12:00:00
        "%d/%m/%Y",           # 01/01/2024
        "%m/%d/%Y",           # 01/01/2024
    ]
    
    for fmt in formats:
        try:
            datetime.strptime(date_str, fmt)
            return True
        except ValueError:
            continue
    
    return False


# ========== QUICK WIN 9: PRECISION, UNITS & LOCALE NORMALIZATION ==========

@dataclass
class MoneyNormalizer:
    """Handles monetary amount normalization with precision and locale support."""
    
    @staticmethod
    def round_currency(amount: Union[str, float, Decimal], currency: str) -> Decimal:
        """Round amount to appropriate decimal places for currency."""
        currency_precision = {
            "USD": 2, "EUR": 2, "GBP": 2, "CAD": 2, "AUD": 2,
            "JPY": 0, "KRW": 0,  # No decimal places
            "BHD": 3, "KWD": 3, "OMR": 3,  # 3 decimal places
            "CLF": 4  # 4 decimal places (special case)
        }
        
        precision = currency_precision.get(currency.upper(), 2)  # Default to 2
        
        if isinstance(amount, str):
            # Parse string amount, handling various formats
            amount = amount.replace(",", "").replace(" ", "")
            amount = Decimal(amount)
        elif isinstance(amount, float):
            amount = Decimal(str(amount))  # Avoid float precision issues
        elif not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        
        # Round to appropriate precision
        if precision == 0:
            return amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        else:
            quantizer = Decimal('0.' + '0' * (precision - 1) + '1')
            return amount.quantize(quantizer, rounding=ROUND_HALF_UP)
    
    @staticmethod
    def normalize_decimal_separator(amount_str: str, locale_code: str = "en_US") -> str:
        """Normalize decimal separator based on locale."""
        locale_separators = {
            "en_US": {"decimal": ".", "thousands": ","},
            "en_GB": {"decimal": ".", "thousands": ","},
            "de_DE": {"decimal": ",", "thousands": "."},
            "fr_FR": {"decimal": ",", "thousands": " "},
            "it_IT": {"decimal": ",", "thousands": "."},
            "es_ES": {"decimal": ",", "thousands": "."},
        }
        
        separators = locale_separators.get(locale_code, locale_separators["en_US"])
        
        # Convert to standard US format (. for decimal, no thousands separator)
        if separators["decimal"] == ",":
            # European format: 1.234,56 -> 1234.56
            parts = amount_str.split(",")
            if len(parts) == 2:
                integer_part = parts[0].replace(".", "").replace(" ", "")
                decimal_part = parts[1]
                return f"{integer_part}.{decimal_part}"
        
        # Remove thousands separators
        return amount_str.replace(",", "")
    
    @staticmethod
    def format_for_locale(amount: Decimal, currency: str, locale_code: str = "en_US") -> str:
        """Format amount according to locale conventions."""
        locale_formats = {
            "en_US": lambda amt, curr: f"{curr} {amt:,.2f}",
            "en_GB": lambda amt, curr: f"{curr} {amt:,.2f}",
            "de_DE": lambda amt, curr: f"{amt:,.2f} {curr}".replace(",", "X").replace(".", ",").replace("X", "."),
            "fr_FR": lambda amt, curr: f"{amt:,.2f} {curr}".replace(",", " ").replace(".", ","),
        }
        
        formatter = locale_formats.get(locale_code, locale_formats["en_US"])
        return formatter(amount, currency)


class UnitConverter:
    """Handle unit conversions in transformations."""
    
    # Conversion factors to base units
    LENGTH_CONVERSIONS = {
        "mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0,
        "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mi": 1609.344
    }
    
    WEIGHT_CONVERSIONS = {
        "mg": 0.000001, "g": 0.001, "kg": 1.0, "t": 1000.0,
        "oz": 0.028349523, "lb": 0.45359237, "st": 6.35029318
    }
    
    @classmethod
    def convert_units(cls, value: float, from_unit: str, to_unit: str, unit_type: str = "length") -> float:
        """Convert between units of same type."""
        conversions = {
            "length": cls.LENGTH_CONVERSIONS,
            "weight": cls.WEIGHT_CONVERSIONS
        }
        
        if unit_type not in conversions:
            raise ValueError(f"Unknown unit type: {unit_type}")
        
        unit_map = conversions[unit_type]
        
        if from_unit not in unit_map:
            raise ValueError(f"Unknown {unit_type} unit: {from_unit}")
        
        if to_unit not in unit_map:
            raise ValueError(f"Unknown {unit_type} unit: {to_unit}")
        
        # Convert to base unit, then to target unit
        base_value = value * unit_map[from_unit]
        return base_value / unit_map[to_unit]


# Function library for use in SFT maps
def money_round(amount: Union[str, float], currency: str) -> str:
    """Round money amount to appropriate precision for currency."""
    rounded = MoneyNormalizer.round_currency(amount, currency)
    return str(rounded)


def money_format(amount: Union[str, float], currency: str, locale: str = "en_US") -> str:
    """Format money amount according to locale."""
    normalized = MoneyNormalizer.round_currency(amount, currency)
    return MoneyNormalizer.format_for_locale(normalized, currency, locale)


def normalize_decimal(amount_str: str, locale: str = "en_US") -> str:
    """Normalize decimal separator for locale."""
    return MoneyNormalizer.normalize_decimal_separator(amount_str, locale)


def convert_length(value: float, from_unit: str, to_unit: str) -> float:
    """Convert length units."""
    return UnitConverter.convert_units(value, from_unit, to_unit, "length")


def convert_weight(value: float, from_unit: str, to_unit: str) -> float:
    """Convert weight units."""
    return UnitConverter.convert_units(value, from_unit, to_unit, "weight")
