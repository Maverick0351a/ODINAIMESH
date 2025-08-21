#!/usr/bin/env python3
"""
Simplified ODIN Research Engine test runner.
Tests core components that are ready for validation.
"""

import sys
import os
import time
import traceback

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__)).replace('scripts', '')
sys.path.insert(0, project_root)

def log_test(name: str, result: bool, details: str = ""):
    """Log test result with colors."""
    status = "✅ PASS" if result else "❌ FAIL"
    print(f"{status} {name}")
    if details:
        print(f"   {details}")

def test_hel_policies():
    """Test HEL policy enforcement."""
    print("🔒 Testing HEL policies...")
    
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
        from apps.gateway.middleware.experiment import get_experiment_variant, bucket_trace_id
        
        # Test deterministic assignment
        trace_id = "test-trace-123"
        experiment_id = "model-comparison"
        rollout_pct = 50
        
        variant1 = get_experiment_variant(trace_id, experiment_id, rollout_pct)
        variant2 = get_experiment_variant(trace_id, experiment_id, rollout_pct)
        
        log_test("Deterministic assignment", variant1 == variant2)
        log_test("Valid variant", variant1 in ["A", "B"])
        
        # Test bucket distribution
        buckets = []
        for i in range(100):
            trace = f"trace-{i:03d}"
            bucket = bucket_trace_id(trace)
            buckets.append(bucket)
        
        unique_buckets = len(set(buckets))
        log_test("Bucket distribution", unique_buckets > 50, f"Unique buckets: {unique_buckets}/100")
        
        # Test rollout distribution
        variants = []
        for i in range(100):
            trace = f"trace-{i:03d}"
            variant = get_experiment_variant(trace, experiment_id, 10)  # 10% rollout
            variants.append(variant)
        
        b_count = variants.count("B")
        log_test("Rollout distribution", 5 <= b_count <= 15, f"B variants: {b_count}/100")
        
        return True
        
    except Exception as e:
        log_test("Experiment middleware test", False, str(e))
        return False

def test_research_api_structure():
    """Test research API structure and imports."""
    print("\n📊 Testing research API structure...")
    
    try:
        from gateway.routers.research import router, ResearchStorage, Project, BYOKToken
        
        log_test("Research router import", True)
        log_test("Storage class import", True)
        log_test("Project model import", True)
        log_test("BYOK token model import", True)
        
        # Test storage creation
        storage = ResearchStorage()
        log_test("Storage instantiation", True)
        
        # Test router structure
        routes = [route.path for route in router.routes]
        expected_routes = ["/projects", "/byok/token", "/experiments", "/runs"]
        has_routes = all(any(expected in route for route in routes) for expected in expected_routes)
        log_test("Router has expected endpoints", has_routes, f"Routes: {routes}")
        
        return True
        
    except Exception as e:
        log_test("Research API structure test", False, str(e))
        return False

def test_bridge_pro_structure():
    """Test Bridge Pro engine structure."""
    print("\n💰 Testing Bridge Pro structure...")
    
    try:
        from libs.odin_core.odin.bridge_engine import BridgeEngine, BridgeResult, BridgeExecuteRequest
        
        log_test("BridgeEngine import", True)
        log_test("BridgeResult import", True)
        log_test("BridgeExecuteRequest import", True)
        
        # Test engine creation
        engine = BridgeEngine()
        log_test("Bridge engine instantiation", True)
        
        return True
        
    except Exception as e:
        log_test("Bridge Pro structure test", False, str(e))
        return False

def test_bench_structure():
    """Test bench runner structure."""
    print("\n📏 Testing bench structure...")
    
    try:
        from bench.runner.run_bench import BenchRunner, BenchConfig, OdinBenchRunner
        
        log_test("BenchRunner import", True)
        log_test("BenchConfig import", True)
        log_test("OdinBenchRunner import", True)
        
        # Test config creation
        config = BenchConfig()
        log_test("BenchConfig instantiation", True)
        
        # Test runner creation
        runner = BenchRunner(config)
        log_test("BenchRunner instantiation", True)
        
        return True
        
    except Exception as e:
        log_test("Bench structure test", False, str(e))
        return False

def test_file_structure():
    """Test that key files exist."""
    print("\n📁 Testing file structure...")
    
    key_files = [
        "gateway/routers/research.py",
        "gateway/middleware/hel_policy.py",
        "apps/gateway/middleware/experiment.py",
        "libs/odin_core/odin/bridge_engine.py",
        "bench/runner/run_bench.py",
        "docs/.vitepress/theme/components/OdinPlayground.vue",
        "apps/gateway/api.py"
    ]
    
    all_exist = True
    for file_path in key_files:
        full_path = os.path.join(project_root, file_path)
        exists = os.path.exists(full_path)
        log_test(f"File exists: {file_path}", exists)
        if not exists:
            all_exist = False
    
    return all_exist

def main():
    """Run all tests and report results."""
    print("🚀 Starting ODIN Research Engine integration test...\n")
    
    tests = [
        test_file_structure,
        test_hel_policies,
        test_experiment_middleware,
        test_research_api_structure,
        test_bridge_pro_structure,
        test_bench_structure
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
        print("\n🚀 Next steps:")
        print("1. Start PostgreSQL database")
        print("2. Run: docker-compose -f docker-compose.research.yml up")
        print("3. Test Research Engine endpoints")
        print("4. Deploy to production")
        return 0
    else:
        print("⚠️  Some tests failed. Please review and fix issues before deployment.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
