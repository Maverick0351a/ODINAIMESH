"""
ISO 20022 Banking Validators for ODIN Payments Bridge Pro

Comprehensive validation suite for ISO 20022 payment messages including:
- IBAN/BIC format validation
- Currency code validation  
- Amount precision validation
- Date/time format validation
- Business rule validation

These validators ensure compliance with banking standards and prevent
costly payment rejections from financial institutions.
"""

import re
import iso3166
from typing import Dict, Any, List, Optional
from decimal import Decimal, InvalidOperation
from datetime import datetime
from enum import Enum


class ValidationSeverity(str, Enum):
    """Validation result severity levels."""
    ERROR = "error"
    WARNING = "warning" 
    INFO = "info"


class CurrencyCode(str, Enum):
    """ISO 4217 currency codes commonly used in payments."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CHF = "CHF"
    CAD = "CAD"
    AUD = "AUD"
    SEK = "SEK"
    NOK = "NOK"
    DKK = "DKK"
    PLN = "PLN"
    CZK = "CZK"
    HUF = "HUF"
    SGD = "SGD"
    HKD = "HKD"


# Currency precision rules (number of decimal places)
CURRENCY_PRECISION = {
    "USD": 2, "EUR": 2, "GBP": 2, "CHF": 2, "CAD": 2, "AUD": 2,
    "SEK": 2, "NOK": 2, "DKK": 2, "PLN": 2, "CZK": 2, "HUF": 2,
    "SGD": 2, "HKD": 2,
    "JPY": 0,  # Japanese Yen has no decimal places
    "KRW": 0,  # Korean Won has no decimal places
    "BHD": 3,  # Bahraini Dinar has 3 decimal places
    "JOD": 3,  # Jordanian Dinar has 3 decimal places
    "KWD": 3,  # Kuwaiti Dinar has 3 decimal places
    "OMR": 3,  # Omani Rial has 3 decimal places
    "TND": 3,  # Tunisian Dinar has 3 decimal places
}


def validate_iban(iban: str) -> Dict[str, Any]:
    """
    Validate International Bank Account Number (IBAN).
    
    Args:
        iban: IBAN string to validate
        
    Returns:
        Dict with validation results including valid flag, errors, and metadata
    """
    if not iban:
        return {
            "valid": False,
            "errors": ["IBAN is required"],
            "metadata": {"input": iban}
        }
    
    # Remove spaces and convert to uppercase
    iban_clean = iban.replace(" ", "").upper()
    
    # Check length (15-34 characters)
    if len(iban_clean) < 15 or len(iban_clean) > 34:
        return {
            "valid": False,
            "errors": [f"IBAN length must be 15-34 characters, got {len(iban_clean)}"],
            "metadata": {"input": iban, "cleaned": iban_clean}
        }
    
    # Check format (2 letter country code + 2 digit check + alphanumeric)
    if not re.match(r'^[A-Z]{2}\d{2}[A-Z0-9]+$', iban_clean):
        return {
            "valid": False,
            "errors": ["IBAN format invalid - must be 2 letters + 2 digits + alphanumeric"],
            "metadata": {"input": iban, "cleaned": iban_clean}
        }
    
    # Extract country code
    country_code = iban_clean[:2]
    
    # Validate country code
    try:
        iso3166.countries.get(country_code)
    except KeyError:
        return {
            "valid": False,
            "errors": [f"Invalid country code: {country_code}"],
            "metadata": {"input": iban, "cleaned": iban_clean, "country_code": country_code}
        }
    
    # Validate IBAN check digits using mod 97 algorithm
    # Move first 4 characters to end and replace letters with numbers
    rearranged = iban_clean[4:] + iban_clean[:4]
    numeric_string = ""
    
    for char in rearranged:
        if char.isalpha():
            # A=10, B=11, ..., Z=35
            numeric_string += str(ord(char) - ord('A') + 10)
        else:
            numeric_string += char
    
    try:
        remainder = int(numeric_string) % 97
        if remainder != 1:
            return {
                "valid": False,
                "errors": ["IBAN check digit validation failed"],
                "metadata": {
                    "input": iban, 
                    "cleaned": iban_clean,
                    "country_code": country_code,
                    "check_remainder": remainder
                }
            }
    except ValueError:
        return {
            "valid": False,
            "errors": ["IBAN contains invalid characters"],
            "metadata": {"input": iban, "cleaned": iban_clean}
        }
    
    return {
        "valid": True,
        "errors": [],
        "metadata": {
            "input": iban,
            "cleaned": iban_clean, 
            "country_code": country_code,
            "format": "ISO 13616"
        }
    }


def validate_bic(bic: str) -> Dict[str, Any]:
    """
    Validate Bank Identifier Code (BIC/SWIFT code).
    
    Args:
        bic: BIC string to validate
        
    Returns:
        Dict with validation results
    """
    if not bic:
        return {
            "valid": False,
            "errors": ["BIC is required"],
            "metadata": {"input": bic}
        }
    
    # Remove spaces and convert to uppercase
    bic_clean = bic.replace(" ", "").upper()
    
    # BIC format: 4 letter bank code + 2 letter country + 2 letter location + optional 3 letter branch
    if not re.match(r'^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$', bic_clean):
        return {
            "valid": False,
            "errors": ["BIC format invalid - must be 8 or 11 characters (AAAABBCCXXX)"],
            "metadata": {"input": bic, "cleaned": bic_clean}
        }
    
    # Check length (8 or 11 characters)
    if len(bic_clean) not in [8, 11]:
        return {
            "valid": False,
            "errors": [f"BIC length must be 8 or 11 characters, got {len(bic_clean)}"],
            "metadata": {"input": bic, "cleaned": bic_clean}
        }
    
    # Extract components
    bank_code = bic_clean[:4]
    country_code = bic_clean[4:6]
    location_code = bic_clean[6:8]
    branch_code = bic_clean[8:11] if len(bic_clean) == 11 else None
    
    # Validate country code
    try:
        iso3166.countries.get(country_code)
    except KeyError:
        return {
            "valid": False,
            "errors": [f"Invalid country code in BIC: {country_code}"],
            "metadata": {
                "input": bic,
                "cleaned": bic_clean,
                "country_code": country_code
            }
        }
    
    return {
        "valid": True,
        "errors": [],
        "metadata": {
            "input": bic,
            "cleaned": bic_clean,
            "bank_code": bank_code,
            "country_code": country_code,
            "location_code": location_code,
            "branch_code": branch_code,
            "format": "ISO 9362"
        }
    }


def validate_currency(currency: str) -> Dict[str, Any]:
    """
    Validate ISO 4217 currency code.
    
    Args:
        currency: 3-letter currency code
        
    Returns:
        Dict with validation results
    """
    if not currency:
        return {
            "valid": False,
            "errors": ["Currency code is required"],
            "metadata": {"input": currency}
        }
    
    currency_upper = currency.upper()
    
    # Check format (3 letters)
    if not re.match(r'^[A-Z]{3}$', currency_upper):
        return {
            "valid": False,
            "errors": ["Currency code must be 3 uppercase letters"],
            "metadata": {"input": currency, "cleaned": currency_upper}
        }
    
    # Check against known currency codes
    try:
        CurrencyCode(currency_upper)
        is_supported = True
    except ValueError:
        is_supported = False
    
    # For validation, we accept any 3-letter code but warn if not in our supported list
    errors = []
    warnings = []
    
    if not is_supported:
        warnings.append(f"Currency {currency_upper} not in supported currency list")
    
    return {
        "valid": True,
        "errors": errors,
        "warnings": warnings,
        "metadata": {
            "input": currency,
            "cleaned": currency_upper,
            "supported": is_supported,
            "format": "ISO 4217"
        }
    }


def validate_amount_precision(amount: Any, currency: str = "EUR") -> Dict[str, Any]:
    """
    Validate amount precision according to currency rules.
    
    Args:
        amount: Amount value (string, number, or Decimal)
        currency: Currency code for precision rules
        
    Returns:
        Dict with validation results
    """
    if amount is None:
        return {
            "valid": False,
            "errors": ["Amount is required"],
            "metadata": {"input": amount, "currency": currency}
        }
    
    # Convert to Decimal for precise arithmetic
    try:
        decimal_amount = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        return {
            "valid": False,
            "errors": [f"Amount must be a valid number, got: {amount}"],
            "metadata": {"input": amount, "currency": currency}
        }
    
    # Check if amount is positive
    if decimal_amount <= 0:
        return {
            "valid": False,
            "errors": ["Amount must be positive"],
            "metadata": {"input": amount, "currency": currency, "decimal_amount": str(decimal_amount)}
        }
    
    # Get expected precision for currency
    currency_upper = currency.upper()
    expected_precision = CURRENCY_PRECISION.get(currency_upper, 2)  # Default to 2 decimal places
    
    # Check decimal places
    decimal_places = decimal_amount.as_tuple().exponent * -1 if decimal_amount.as_tuple().exponent < 0 else 0
    
    if decimal_places > expected_precision:
        return {
            "valid": False,
            "errors": [f"Amount has {decimal_places} decimal places, {currency_upper} allows maximum {expected_precision}"],
            "metadata": {
                "input": amount,
                "currency": currency_upper,
                "decimal_amount": str(decimal_amount),
                "decimal_places": decimal_places,
                "expected_precision": expected_precision
            }
        }
    
    # Check maximum amount (most systems have limits)
    max_amount = Decimal("999999999.99")  # 1 billion - 1 cent
    if decimal_amount > max_amount:
        return {
            "valid": False,
            "errors": [f"Amount exceeds maximum allowed: {max_amount}"],
            "metadata": {
                "input": amount,
                "currency": currency_upper,
                "decimal_amount": str(decimal_amount),
                "max_amount": str(max_amount)
            }
        }
    
    return {
        "valid": True,
        "errors": [],
        "metadata": {
            "input": amount,
            "currency": currency_upper,
            "decimal_amount": str(decimal_amount),
            "decimal_places": decimal_places,
            "expected_precision": expected_precision,
            "minor_units": int(decimal_amount * (10 ** expected_precision))
        }
    }


def validate_credtm_iso8601(datetime_str: str) -> Dict[str, Any]:
    """
    Validate credit datetime in ISO 8601 format.
    
    Args:
        datetime_str: ISO 8601 datetime string
        
    Returns:
        Dict with validation results
    """
    if not datetime_str:
        return {
            "valid": False,
            "errors": ["Credit datetime is required"],
            "metadata": {"input": datetime_str}
        }
    
    # Try to parse various ISO 8601 formats
    iso_formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",      # 2023-12-25T14:30:45.123Z
        "%Y-%m-%dT%H:%M:%SZ",         # 2023-12-25T14:30:45Z
        "%Y-%m-%dT%H:%M:%S.%f%z",     # 2023-12-25T14:30:45.123+01:00
        "%Y-%m-%dT%H:%M:%S%z",        # 2023-12-25T14:30:45+01:00
        "%Y-%m-%dT%H:%M:%S",          # 2023-12-25T14:30:45
        "%Y-%m-%d",                   # 2023-12-25 (date only)
    ]
    
    parsed_datetime = None
    format_used = None
    
    for fmt in iso_formats:
        try:
            parsed_datetime = datetime.strptime(datetime_str, fmt)
            format_used = fmt
            break
        except ValueError:
            continue
    
    if parsed_datetime is None:
        return {
            "valid": False,
            "errors": ["Invalid ISO 8601 datetime format"],
            "metadata": {
                "input": datetime_str,
                "expected_formats": iso_formats
            }
        }
    
    # Check if date is not too far in the past or future
    now = datetime.utcnow()
    days_diff = abs((parsed_datetime.replace(tzinfo=None) - now).days)
    
    warnings = []
    if days_diff > 365:  # More than 1 year difference
        warnings.append(f"Date is {days_diff} days from current date")
    
    return {
        "valid": True,
        "errors": [],
        "warnings": warnings,
        "metadata": {
            "input": datetime_str,
            "parsed": parsed_datetime.isoformat(),
            "format_used": format_used,
            "days_from_now": days_diff
        }
    }


def validate_sum_check(payment_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate sum checks and totals in payment message.
    
    Args:
        payment_data: Payment message data
        
    Returns:
        Dict with validation results
    """
    errors = []
    warnings = []
    metadata = {"checks_performed": []}
    
    # Check if control sum matches individual transactions
    if "group_header" in payment_data and "control_sum" in payment_data["group_header"]:
        control_sum = Decimal(str(payment_data["group_header"]["control_sum"]))
        metadata["control_sum"] = str(control_sum)
        metadata["checks_performed"].append("control_sum")
        
        # Calculate sum of individual transactions
        calculated_sum = Decimal("0")
        transaction_count = 0
        
        if "payment_information" in payment_data:
            for payment_info in payment_data["payment_information"]:
                if "credit_transfer_transaction_information" in payment_info:
                    for txn in payment_info["credit_transfer_transaction_information"]:
                        if "instructed_amount" in txn and "amount" in txn["instructed_amount"]:
                            try:
                                amount = Decimal(str(txn["instructed_amount"]["amount"]))
                                calculated_sum += amount
                                transaction_count += 1
                            except (InvalidOperation, ValueError):
                                errors.append(f"Invalid amount in transaction: {txn['instructed_amount']['amount']}")
        
        metadata["calculated_sum"] = str(calculated_sum)
        metadata["transaction_count"] = transaction_count
        
        if calculated_sum != control_sum:
            errors.append(f"Control sum mismatch: declared {control_sum}, calculated {calculated_sum}")
    
    # Check number of transactions
    if "group_header" in payment_data and "number_of_transactions" in payment_data["group_header"]:
        declared_count = payment_data["group_header"]["number_of_transactions"]
        
        # Count actual transactions (already calculated above)
        if "transaction_count" in metadata:
            actual_count = metadata["transaction_count"]
            if declared_count != actual_count:
                errors.append(f"Transaction count mismatch: declared {declared_count}, found {actual_count}")
        
        metadata["declared_transaction_count"] = declared_count
        metadata["checks_performed"].append("transaction_count")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "metadata": metadata
    }


def validate_end_to_end_id(end_to_end_id: str) -> Dict[str, Any]:
    """
    Validate End-to-End identification.
    
    Args:
        end_to_end_id: End-to-End ID string
        
    Returns:
        Dict with validation results
    """
    if not end_to_end_id:
        return {
            "valid": False,
            "errors": ["End-to-End ID is required"],
            "metadata": {"input": end_to_end_id}
        }
    
    # Max length 35 characters
    if len(end_to_end_id) > 35:
        return {
            "valid": False,
            "errors": [f"End-to-End ID exceeds 35 characters: {len(end_to_end_id)}"],
            "metadata": {"input": end_to_end_id, "length": len(end_to_end_id)}
        }
    
    # Should contain only valid characters (alphanumeric and limited special chars)
    if not re.match(r'^[A-Za-z0-9\-\.\?\:\(\)\+\'\/\s]+$', end_to_end_id):
        return {
            "valid": False,
            "errors": ["End-to-End ID contains invalid characters"],
            "metadata": {"input": end_to_end_id, "allowed_pattern": r'^[A-Za-z0-9\-\.\?\:\(\)\+\'\/\s]+$'}
        }
    
    return {
        "valid": True,
        "errors": [],
        "metadata": {
            "input": end_to_end_id,
            "length": len(end_to_end_id),
            "format": "ISO 20022 text"
        }
    }


def run_comprehensive_validation(payment_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run comprehensive validation suite on ISO 20022 payment message.
    
    Args:
        payment_data: Complete payment message data
        
    Returns:
        Dict with comprehensive validation results
    """
    results = {
        "overall_valid": True,
        "validators": [],
        "summary": {
            "total_checks": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }
    }
    
    # Extract key fields for validation
    fields_to_validate = {
        "debtor_account_iban": None,
        "creditor_agent_bic": None,
        "instructed_amount": None,
        "instructed_currency": None,
        "requested_execution_date": None,
        "end_to_end_id": None
    }
    
    # Navigate payment structure to extract fields
    if "payment_information" in payment_data:
        for payment_info in payment_data["payment_information"]:
            # Get debtor account IBAN
            if "debtor_account" in payment_info and "identification" in payment_info["debtor_account"]:
                fields_to_validate["debtor_account_iban"] = payment_info["debtor_account"]["identification"].get("iban")
            
            # Get requested execution date
            if "requested_execution_date" in payment_info:
                fields_to_validate["requested_execution_date"] = payment_info["requested_execution_date"]
            
            # Get transaction-level fields
            if "credit_transfer_transaction_information" in payment_info:
                for txn in payment_info["credit_transfer_transaction_information"]:
                    # Get creditor agent BIC
                    if "creditor_agent" in txn and "financial_institution_identification" in txn["creditor_agent"]:
                        fields_to_validate["creditor_agent_bic"] = txn["creditor_agent"]["financial_institution_identification"].get("bic")
                    
                    # Get amount and currency
                    if "instructed_amount" in txn:
                        fields_to_validate["instructed_amount"] = txn["instructed_amount"].get("amount")
                        fields_to_validate["instructed_currency"] = txn["instructed_amount"].get("currency")
                    
                    # Get End-to-End ID
                    if "payment_identification" in txn and "end_to_end_identification" in txn["payment_identification"]:
                        fields_to_validate["end_to_end_id"] = txn["payment_identification"]["end_to_end_identification"]
                    
                    break  # Use first transaction for demo
            break  # Use first payment info for demo
    
    # Run individual validators
    validators = [
        ("iban", lambda: validate_iban(fields_to_validate["debtor_account_iban"] or "")),
        ("bic", lambda: validate_bic(fields_to_validate["creditor_agent_bic"] or "")),
        ("currency", lambda: validate_currency(fields_to_validate["instructed_currency"] or "")),
        ("amount_precision", lambda: validate_amount_precision(fields_to_validate["instructed_amount"], fields_to_validate["instructed_currency"] or "EUR")),
        ("execution_date", lambda: validate_credtm_iso8601(fields_to_validate["requested_execution_date"] or "")),
        ("end_to_end_id", lambda: validate_end_to_end_id(fields_to_validate["end_to_end_id"] or "")),
        ("sum_check", lambda: validate_sum_check(payment_data)),
    ]
    
    for validator_name, validator_func in validators:
        try:
            result = validator_func()
            results["validators"].append({
                "name": validator_name,
                "valid": result["valid"],
                "errors": result.get("errors", []),
                "warnings": result.get("warnings", []),
                "metadata": result.get("metadata", {})
            })
            
            results["summary"]["total_checks"] += 1
            
            if result["valid"]:
                results["summary"]["passed"] += 1
            else:
                results["summary"]["failed"] += 1
                results["overall_valid"] = False
            
            if result.get("warnings"):
                results["summary"]["warnings"] += len(result["warnings"])
                
        except Exception as e:
            results["validators"].append({
                "name": validator_name,
                "valid": False,
                "errors": [f"Validator error: {str(e)}"],
                "warnings": [],
                "metadata": {"exception": str(e)}
            })
            results["summary"]["total_checks"] += 1
            results["summary"]["failed"] += 1
            results["overall_valid"] = False
    
    return results
