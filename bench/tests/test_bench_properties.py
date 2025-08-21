"""
Property tests for ODIN-Bench validation.

Run with: pytest bench/tests/test_bench_properties.py
"""

import pytest
import json
from pathlib import Path

def load_last_report():
    """Load the last benchmark report."""
    report_file = Path(__file__).parent.parent / "reports" / "last_run.json" 
    if not report_file.exists():
        pytest.skip("No benchmark report found. Run bench/runner/run_bench.py first.")
    
    with open(report_file) as f:
        return json.load(f)

class TestTranslationProperties:
    """Property tests for translation benchmarks."""
    
    def test_coverage_target(self):
        """Coverage must be >= 95%."""
        report = load_last_report()
        coverage = report["translation"]["coverage_pct"]
        assert coverage >= 95.0, f"Coverage {coverage}% below target 95%"
    
    def test_no_missing_required_fields(self):
        """No missing required fields allowed."""
        report = load_last_report()
        # This would need to be tracked in the report
        # For now, check that all translation cases passed
        cases_run = report["translation"]["cases_run"]
        cases_passed = report["translation"]["cases_passed"]
        assert cases_passed == cases_run, f"Some translation cases failed: {cases_passed}/{cases_run}"
    
    def test_no_enum_violations(self):
        """No enum violations allowed."""
        report = load_last_report()
        violations = report["translation"]["enum_violations"]
        assert violations == 0, f"Found {violations} enum violations"
    
    def test_round_trip_success(self):
        """Round-trip translation must succeed."""
        report = load_last_report()
        round_trip_count = report["translation"]["round_trip_ok"]
        cases_run = report["translation"]["cases_run"]
        
        # All cases should support round-trip
        assert round_trip_count == cases_run, f"Round-trip failed: {round_trip_count}/{cases_run}"
    
    def test_p95_latency_target(self):
        """P95 latency must be <= 50ms."""
        report = load_last_report()
        p95_time = report["translation"]["p95_time_ms"]
        assert p95_time <= 50.0, f"P95 latency {p95_time}ms exceeds target 50ms"

class TestGovernanceProperties:
    """Property tests for governance/HEL benchmarks."""
    
    def test_no_false_allow_pii(self):
        """No false allows for PII cases."""
        # TODO: implement when governance tests are added
        pass
    
    def test_policy_eval_performance(self):
        """Policy evaluation must be <= 5ms P95."""
        # TODO: implement when governance tests are added
        pass

class TestReceiptProperties:
    """Property tests for receipt continuity."""
    
    def test_chain_continuity_target(self):
        """Chain continuity must be >= 99.9%."""
        # TODO: implement when receipt tests are added
        pass
    
    def test_no_receipt_write_failures(self):
        """No receipt write failures allowed."""
        # TODO: implement when receipt tests are added
        pass

class TestRouterProperties:
    """Property tests for cost/latency router."""
    
    def test_fallback_rate_limit(self):
        """Fallback rate must be <= 20%."""
        # TODO: implement when router tests are added
        pass
    
    def test_cost_per_request_target(self):
        """Cost per request must meet target."""
        # TODO: implement when router tests are added
        pass
    
    def test_p95_latency_slo(self):
        """P95 latency must meet SLO."""
        # TODO: implement when router tests are added  
        pass

# Smoke test to ensure report structure
def test_report_structure():
    """Verify benchmark report has expected structure."""
    report = load_last_report()
    
    required_fields = ["timestamp", "total_cases", "passed", "failed", "translation"]
    for field in required_fields:
        assert field in report, f"Missing field in report: {field}"
    
    # Check translation metrics structure
    translation = report["translation"]
    required_translation_fields = ["cases_run", "cases_passed", "coverage_pct", "avg_time_ms", "p95_time_ms"]
    for field in required_translation_fields:
        assert field in translation, f"Missing translation metric: {field}"
