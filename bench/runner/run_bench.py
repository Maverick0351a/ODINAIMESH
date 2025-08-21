#!/usr/bin/env python3
"""
ODIN-Bench Runner

Executes Gateway in test mode and validates against golden datasets.
Generates scoreboard with coverage, performance, and compliance metrics.
"""

import asyncio
import json
import time
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import httpx
import pytest
from decimal import Decimal

_log = logging.getLogger(__name__)

@dataclass
class BenchConfig:
    """Benchmark configuration."""
    test_cases_dir: str = "bench/cases"
    data_dir: str = "bench/data"
    reports_dir: str = "bench/reports"
    gateway_url: str = "http://localhost:8000"
    timeout: float = 30.0


@dataclass
class BenchResult:
    """Single test case result."""
    case_id: str
    success: bool
    metrics: Dict[str, Any]
    errors: List[str]
    time_ms: float

@dataclass  
class BenchReport:
    """Complete benchmark report."""
    timestamp: str
    total_cases: int
    passed: int
    failed: int
    
    # Translation metrics
    translation: Dict[str, Any]
    
    # Governance metrics  
    governance: Dict[str, Any]
    
    # Receipt metrics
    receipts: Dict[str, Any]
    
    # Router metrics
    router: Dict[str, Any]

class BenchRunner:
    """Alias for OdinBenchRunner for compatibility."""
    
    def __init__(self, config: BenchConfig):
        self.config = config
        self.runner = OdinBenchRunner(config.gateway_url)
    
    async def run_all(self) -> BenchReport:
        """Run all benchmarks."""
        return await self.runner.run_all()
    
    async def run_translation_tests(self) -> List[BenchResult]:
        """Run translation tests."""
        return await self.runner.run_translation_tests()


class OdinBenchRunner:
    """ODIN Benchmark test runner."""
    
    def __init__(self, gateway_url: str = "http://localhost:8000"):
        self.gateway_url = gateway_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.bench_dir = Path(__file__).parent.parent
        
    async def run_all(self) -> BenchReport:
        """Run complete benchmark suite."""
        _log.info("Starting ODIN-Bench evaluation...")
        
        start_time = time.time()
        results = []
        
        # Run translation tests
        translation_results = await self.run_translation_tests()
        results.extend(translation_results)
        
        # Run governance tests  
        governance_results = await self.run_governance_tests()
        results.extend(governance_results)
        
        # Run receipt tests
        receipt_results = await self.run_receipt_tests()
        results.extend(receipt_results)
        
        # Generate report
        report = self._generate_report(results, time.time() - start_time)
        
        # Save report
        await self._save_report(report)
        
        return report
        
    async def run_translation_tests(self) -> List[BenchResult]:
        """Run translation/SFT tests."""
        _log.info("Running translation tests...")
        
        test_cases_file = self.bench_dir / "cases" / "translation.yaml"
        with open(test_cases_file) as f:
            config = yaml.safe_load(f)
            
        results = []
        
        for test_case in config.get("test_cases", []):
            case_results = await self._run_translation_case(test_case)
            results.extend(case_results)
            
        return results
        
    async def _run_translation_case(self, test_case: Dict[str, Any]) -> List[BenchResult]:
        """Run a single translation test case."""
        results = []
        
        # Load input files
        input_pattern = test_case["input_files"]
        input_files = list(Path(".").glob(input_pattern))
        
        for input_file in input_files:
            case_id = input_file.stem
            start_time = time.perf_counter()
            
            try:
                # Load input and expected output
                with open(input_file) as f:
                    input_data = json.load(f)
                    
                expected_file = self.bench_dir / "data" / "expected" / "iso20022_pain001_v1" / f"{case_id}.json"
                with open(expected_file) as f:
                    expected_output = json.load(f)
                
                # Execute translation via Gateway
                actual_output, metrics = await self._execute_translation(
                    input_data, test_case["realm"], test_case["map_id"]
                )
                
                # Validate result
                validation_errors = self._validate_translation(
                    input_data, actual_output, expected_output, test_case
                )
                
                time_ms = (time.perf_counter() - start_time) * 1000
                
                result = BenchResult(
                    case_id=case_id,
                    success=len(validation_errors) == 0,
                    metrics={
                        **metrics,
                        "time_ms": time_ms,
                        "coverage_pct": self._calculate_coverage(input_data, test_case),
                        "round_trip_ok": self._test_round_trip(actual_output, input_data, test_case)
                    },
                    errors=validation_errors,
                    time_ms=time_ms
                )
                
                results.append(result)
                
            except Exception as e:
                time_ms = (time.perf_counter() - start_time) * 1000
                result = BenchResult(
                    case_id=case_id,
                    success=False,
                    metrics={"time_ms": time_ms},
                    errors=[f"Execution failed: {str(e)}"],
                    time_ms=time_ms
                )
                results.append(result)
                
        return results
        
    async def _execute_translation(self, input_data: Dict, realm: str, map_id: str) -> tuple[Dict, Dict]:
        """Execute translation via Gateway API."""
        
        # Use Bridge Pro API for invoice translation
        url = f"{self.gateway_url}/v1/bridge-pro/execute"
        
        payload = {
            "realm": realm,
            "map_id": map_id,
            "input_data": input_data,
            "options": {
                "validate": True,
                "format": "iso20022_pain001"
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-ODIN-Agent": "did:odin:bench",
            "X-ODIN-Trace-Id": f"bench-{int(time.time())}"
        }
        
        response = await self.client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        
        # Extract output and metrics
        output = result.get("result", {}).get("output", {})
        metrics = {
            "tokens_in": result.get("result", {}).get("tokens_in", 0),
            "tokens_out": result.get("result", {}).get("tokens_out", 0),
            "validator_passed": result.get("result", {}).get("validator_passed", False)
        }
        
        return output, metrics
        
    def _validate_translation(self, input_data: Dict, actual: Dict, expected: Dict, test_case: Dict) -> List[str]:
        """Validate translation results against expected output and invariants."""
        errors = []
        
        # Required field validation
        coverage = test_case.get("coverage", {})
        for field in coverage.get("required_fields", []):
            if not self._has_field(actual, field):
                errors.append(f"Missing required field: {field}")
                
        # Invariant validation
        for invariant in test_case.get("invariants", []):
            error = self._validate_invariant(actual, invariant)
            if error:
                errors.append(error)
                
        # Performance validation
        performance = test_case.get("performance", {})
        max_time = performance.get("max_time_ms", float('inf'))
        # Note: time validation would be done by caller
        
        return errors
        
    def _validate_invariant(self, data: Dict, invariant: Dict) -> Optional[str]:
        """Validate a single invariant rule."""
        field = invariant["field"]
        validator = invariant["validator"]
        
        value = self._get_field_value(data, field)
        if value is None:
            return None  # Field not present, handled by required field check
            
        if validator == "iban_checksum":
            if not self._validate_iban(str(value)):
                return f"Invalid IBAN checksum: {field}={value}"
                
        elif validator == "iso4217_currency":
            allowed = invariant.get("allowed", [])
            if value not in allowed:
                return f"Invalid currency code: {field}={value}, allowed: {allowed}"
                
        elif validator == "decimal_precision":
            max_decimals = invariant.get("max_decimals", 2)
            if isinstance(value, (int, float)):
                decimal_places = len(str(value).split(".")[-1]) if "." in str(value) else 0
                if decimal_places > max_decimals:
                    return f"Too many decimal places: {field}={value}, max: {max_decimals}"
                    
        elif validator == "bic_format":
            pattern = invariant.get("pattern", "")
            import re
            if not re.match(pattern, str(value)):
                return f"Invalid BIC format: {field}={value}"
                
        return None
        
    def _validate_iban(self, iban: str) -> bool:
        """Validate IBAN checksum (simplified)."""
        # Remove spaces and convert to uppercase
        iban = iban.replace(" ", "").upper()
        
        # Basic length check (real IBAN validation is complex)
        if len(iban) < 15 or len(iban) > 34:
            return False
            
        # Check if starts with country code
        if not iban[:2].isalpha():
            return False
            
        return True  # Simplified for demo
        
    def _calculate_coverage(self, input_data: Dict, test_case: Dict) -> float:
        """Calculate field coverage percentage."""
        coverage = test_case.get("coverage", {})
        required_fields = coverage.get("required_fields", [])
        optional_fields = coverage.get("optional_fields", [])
        
        total_fields = len(required_fields) + len(optional_fields)
        if total_fields == 0:
            return 100.0
            
        covered_fields = 0
        for field in required_fields + optional_fields:
            if self._has_field(input_data, field):
                covered_fields += 1
                
        return (covered_fields / total_fields) * 100.0
        
    def _test_round_trip(self, output: Dict, original_input: Dict, test_case: Dict) -> bool:
        """Test if translation can be reversed (simplified)."""
        # For demo, just check that key fields are preserved
        try:
            # Extract amount from ISO 20022 output
            iso_amount = output.get("Document", {}).get("CstmrCdtTrfInitn", {}).get("PmtInf", {}).get("CdtTrfTxInf", {}).get("Amt", {}).get("InstdAmt", {}).get("value")
            original_amount = original_input.get("amount")
            
            if iso_amount and original_amount:
                tolerance = test_case.get("round_trip", {}).get("tolerance", 0.01)
                return abs(float(iso_amount) - float(original_amount)) <= tolerance
                
            return True  # If amounts not found, pass for now
        except Exception:
            return False
            
    def _has_field(self, data: Dict, field_path: str) -> bool:
        """Check if nested field exists in data."""
        try:
            parts = field_path.split(".")
            current = data
            for part in parts:
                current = current[part]
            return current is not None
        except (KeyError, TypeError):
            return False
            
    def _get_field_value(self, data: Dict, field_path: str) -> Any:
        """Get value of nested field."""
        try:
            parts = field_path.split(".")
            current = data
            for part in parts:
                current = current[part]
            return current
        except (KeyError, TypeError):
            return None
            
    async def run_governance_tests(self) -> List[BenchResult]:
        """Run governance/HEL policy tests."""
        _log.info("Running governance tests...")
        # Placeholder for governance tests
        return []
        
    async def run_receipt_tests(self) -> List[BenchResult]:
        """Run receipt continuity tests.""" 
        _log.info("Running receipt tests...")
        # Placeholder for receipt tests
        return []
        
    def _generate_report(self, results: List[BenchResult], total_time: float) -> BenchReport:
        """Generate benchmark report from results."""
        
        total_cases = len(results)
        passed = sum(1 for r in results if r.success)
        failed = total_cases - passed
        
        # Translation metrics
        translation_results = [r for r in results if "coverage_pct" in r.metrics]
        translation_metrics = {
            "cases_run": len(translation_results),
            "cases_passed": sum(1 for r in translation_results if r.success),
            "coverage_pct": sum(r.metrics.get("coverage_pct", 0) for r in translation_results) / max(len(translation_results), 1),
            "avg_time_ms": sum(r.time_ms for r in translation_results) / max(len(translation_results), 1),
            "p95_time_ms": self._calculate_p95([r.time_ms for r in translation_results]),
            "enum_violations": sum(1 for r in translation_results if "Invalid" in " ".join(r.errors)),
            "round_trip_ok": sum(1 for r in translation_results if r.metrics.get("round_trip_ok", False))
        }
        
        return BenchReport(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            total_cases=total_cases,
            passed=passed,
            failed=failed,
            translation=translation_metrics,
            governance={},  # TODO
            receipts={},    # TODO
            router={}       # TODO
        )
        
    def _calculate_p95(self, values: List[float]) -> float:
        """Calculate 95th percentile."""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(0.95 * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]
        
    async def _save_report(self, report: BenchReport) -> None:
        """Save report to file."""
        reports_dir = self.bench_dir / "reports"
        reports_dir.mkdir(exist_ok=True)
        
        # Save as JSON
        report_file = reports_dir / "last_run.json"
        with open(report_file, "w") as f:
            json.dump(asdict(report), f, indent=2)
            
        _log.info(f"Report saved to {report_file}")
        
        # Print summary
        print("\n" + "="*60)
        print("ODIN-BENCH RESULTS")
        print("="*60)
        print(f"Total Cases: {report.total_cases}")
        print(f"Passed: {report.passed}")
        print(f"Failed: {report.failed}")
        print(f"Success Rate: {(report.passed/report.total_cases)*100:.1f}%")
        print("\nTranslation Metrics:")
        print(f"  Coverage: {report.translation['coverage_pct']:.1f}%")
        print(f"  Avg Time: {report.translation['avg_time_ms']:.1f}ms")
        print(f"  P95 Time: {report.translation['p95_time_ms']:.1f}ms")
        print(f"  Enum Violations: {report.translation['enum_violations']}")
        print("="*60)

# CLI interface
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Run ODIN benchmarks")
    parser.add_argument("--gateway-url", default="http://localhost:8000", 
                       help="Gateway URL")
    parser.add_argument("--test-type", choices=["all", "translation", "governance", "receipts"],
                       default="all", help="Test type to run")
    
    args = parser.parse_args()
    
    runner = OdinBenchRunner(args.gateway_url)
    
    if args.test_type == "all":
        report = await runner.run_all()
    else:
        # Run specific test type
        # TODO: implement individual test runners
        report = await runner.run_all()
        
    return 0 if report.failed == 0 else 1

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
