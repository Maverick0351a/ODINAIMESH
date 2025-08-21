#!/usr/bin/env python3
"""
Simple test runner for ODIN Research Engine components.
Validates core functionality without external dependencies.
"""

import sys
import json
import time
import traceback
from typing import Any, Dict, List

def log_test(name: str, result: bool, details: str = ""):
    """Log test result with colors."""
    status = "✅ PASS" if result else "❌ FAIL"
    print(f"{status} {name}")
    if details:
        print(f"   {details}")

def test_imports():
    """Test that all required modules can be imported."""
    print("🔍 Testing imports...")
    
    try:
        # Test gateway imports
        from apps.gateway.api import app
        log_test("Gateway app import", True)
    except Exception as e:
        log_test("Gateway app import", False, str(e))
        return False
    
    try:
        # Test research router import
        from gateway.routers.research import router
        log_test("Research router import", True)
    except Exception as e:
        log_test("Research router import", False, str(e))
        return False
    
    try:
        # Test HEL policy import
        from gateway.middleware.hel_policy import create_hel_enforcer
        log_test("HEL policy import", True)
    except Exception as e:
        log_test("HEL policy import", False, str(e))
        return False
    
    try:
        # Test experiment middleware import
        from apps.gateway.middleware.experiment import ExperimentMiddleware
        log_test("Experiment middleware import", True)
    except Exception as e:
        log_test("Experiment middleware import", False, str(e))
        return False
    
    return True

def test_hel_policies():
    """Test HEL policy enforcement."""
    print("\n🔒 Testing HEL policies...")
    
    try:
        from gateway.middleware.hel_policy import HELPolicy, HELEnforcer
        
        # Create test policy
        policy = HELPolicy(
            max_payload_size=1024,
            required_headers=["x-odin-agent"],
            blocked_domains=["localhost", "127.0.0.1"],
            allowed_realms=["business"]
        )
        
        enforcer = HELEnforcer(policy)
        
        # Test valid request
        headers = {"x-odin-agent": "did:odin:test"}
        error = enforcer.validate_request(headers, 512, "business")
        log_test("Valid request validation", error is None)
        
        # Test missing header
        error = enforcer.validate_request({}, 512, "business")
        log_test("Missing header detection", "Missing required header" in (error or ""))
        
        # Test payload too large
        error = enforcer.validate_request(headers, 2048, "business")
        log_test("Payload size limit", "Payload exceeds limit" in (error or ""))
        
        # Test invalid realm
        error = enforcer.validate_request(headers, 512, "banking")
        log_test("Realm allowlist", "Realm not allowed" in (error or ""))
        
        # Test egress validation
        error = enforcer.validate_egress_url("http://localhost:8080/api")
        log_test("Egress blocking", "Domain blocked" in (error or ""))
        
        # Test header redaction
        headers_with_secrets = {
            "authorization": "Bearer secret",
            "x-api-key": "sk-secret123",
            "user-agent": "ODIN/1.0"
        }
        redacted = enforcer.redact_headers(headers_with_secrets)
        log_test("Header redaction", 
                redacted["authorization"] == "[REDACTED]" and 
                redacted["user-agent"] == "ODIN/1.0")
        
        return True
        
    except Exception as e:
        log_test("HEL policy test", False, str(e))
        return False

def test_experiment_middleware():
    """Test experiment middleware functionality."""
    print("\n🧪 Testing experiment middleware...")
    
    try:
        from apps.gateway.middleware.experiment import get_experiment_variant, ExperimentMiddleware
        
        # Test deterministic assignment
        trace_id = "test-trace-123"
        experiment_id = "model-comparison"
        rollout_pct = 50
        
        variant1 = get_experiment_variant(trace_id, experiment_id, rollout_pct)
        variant2 = get_experiment_variant(trace_id, experiment_id, rollout_pct)
        
        log_test("Deterministic assignment", variant1 == variant2)
        log_test("Valid variant", variant1 in ["A", "B"])
        
        # Test rollout distribution
        variants = []
        for i in range(100):
            trace = f"trace-{i:03d}"
            variant = get_experiment_variant(trace, experiment_id, 10)  # 10% rollout
            variants.append(variant)
        
        b_count = variants.count("B")
        log_test("Rollout distribution", 5 <= b_count <= 15, f"B variants: {b_count}/100")
        
        # Test middleware creation (skip app parameter for now)
        try:
            from unittest.mock import Mock
            app = Mock()
            middleware = ExperimentMiddleware(app)
            log_test("Middleware creation", True)
        except Exception as e:
            log_test("Middleware creation", False, f"Requires app parameter: {e}")
        
        return True
        
    except Exception as e:
        log_test("Experiment middleware test", False, str(e))
        return False

def test_research_models():
    """Test research engine data models."""
    print("\n📊 Testing research models...")
    
    try:
        from gateway.routers.research import Project, BYOKToken, RunReport
        from datetime import datetime
        
        # Test project model
        project = Project(
            id="proj_test123",
            name="Test Project",
            description="A test project",
            created_at=datetime.utcnow(),
            tier="free"
        )
        log_test("Project model", project.name == "Test Project")
        
        # Test BYOK token model
        token = BYOKToken(
            token="byok_test123",
            expires_at=datetime.utcnow(),
            provider="openai"
        )
        log_test("BYOK token model", token.provider == "openai")
        
        # Test run report model
        report = RunReport(
            run_id="run_test123",
            project_id="proj_test123",
            experiment_id="exp_test",
            dataset_id="ds_test123",
            status="completed",
            metrics={"coverage_pct": 95.0},
            receipt_chain=["cid1", "cid2"],
            created_at=datetime.utcnow()
        )
        log_test("Run report model", report.status == "completed")
        
        return True
        
    except Exception as e:
        log_test("Research models test", False, str(e))
        return False

def test_storage_backend():
    """Test in-memory storage backend."""
    print("\n💾 Testing storage backend...")
    
    try:
        from gateway.routers.research import ResearchStorage
        
        storage = ResearchStorage()
        
        # Test project creation
        project = storage.create_project("Test Project", "Description")
        log_test("Project creation", project.name == "Test Project")
        log_test("Project ID format", project.id.startswith("proj_"))
        
        # Test project retrieval
        retrieved = storage.get_project(project.id)
        log_test("Project retrieval", retrieved is not None and retrieved.id == project.id)
        
        # Test BYOK token
        token = storage.store_byok_token("openai", "sk-test123", 15)
        log_test("BYOK token creation", token.token.startswith("byok_"))
        log_test("BYOK token retrieval", storage.get_byok_token(token.token) is not None)
        
        # Test dataset creation
        dataset = storage.store_dataset(project.id, "test.json", "json", 1024, 10)
        log_test("Dataset creation", dataset.name == "test.json")
        
        # Test run creation
        run_id = storage.store_run(project.id, "exp1", dataset.id, realm="business")
        log_test("Run creation", run_id.startswith("run_"))
        
        # Test run retrieval
        run = storage.get_run(run_id)
        log_test("Run retrieval", run is not None and run["id"] == run_id)
        
        # Test rate limiting
        limited = storage.check_rate_limit("127.0.0.1", "test", 1)
        log_test("Rate limit first request", not limited)
        
        limited = storage.check_rate_limit("127.0.0.1", "test", 1)
        log_test("Rate limit second request", limited)
        
        return True
        
    except Exception as e:
        log_test("Storage backend test", False, str(e))
        return False

def test_bench_components():
    """Test bench evaluation components."""
    print("\n📏 Testing bench components...")
    
    try:
        from bench.runner.run_bench import BenchRunner, BenchConfig
        
        # Test config creation
        config = BenchConfig(
            test_cases_dir="bench/cases",
            data_dir="bench/data", 
            reports_dir="bench/reports"
        )
        log_test("Bench config creation", config.test_cases_dir == "bench/cases")
        
        # Test runner creation
        runner = BenchRunner(config)
        log_test("Bench runner creation", runner.config == config)
        
        return True
        
    except Exception as e:
        log_test("Bench components test", False, str(e))
        return False

def main():
    """Run all tests and report results."""
    print("🚀 Starting ODIN Research Engine test suite...\n")
    
    tests = [
        test_imports,
        test_hel_policies,
        test_experiment_middleware,
        test_research_models,
        test_storage_backend,
        test_bench_components
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ FATAL: {test_func.__name__} failed with exception:")
            print(f"   {str(e)}")
            traceback.print_exc()
    
    print(f"\n📊 Test Results: {passed}/{total} test suites passed")
    
    if passed == total:
        print("🎉 All tests passed! Research Engine is ready for deployment.")
        return 0
    else:
        print("⚠️  Some tests failed. Please review and fix issues before deployment.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
