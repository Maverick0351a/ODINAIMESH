"""
Test suite for ODIN Research Engine.

Tests project creation, BYOK tokens, experiments, runs, and safety guardrails.
"""

import pytest
import json
import time
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import the app
from apps.gateway.api import app

client = TestClient(app)


class TestResearchEngine:
    """Test suite for Research Engine functionality."""
    
    def test_health_check(self):
        """Test Research Engine health endpoint."""
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "projects" in data
        assert "active_tokens" in data
    
    def test_create_project_success(self):
        """Test successful project creation."""
        response = client.post(
            "/v1/projects",
            json={
                "name": "Test Project",
                "description": "A test research project"
            },
            headers={"X-ODIN-Agent": "did:odin:test"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Project"
        assert data["description"] == "A test research project"
        assert data["tier"] == "free"
        assert data["quota_requests_limit"] == 1000
        assert data["id"].startswith("proj_")
        return data["id"]
    
    def test_create_project_rate_limit(self):
        """Test project creation rate limiting."""
        # Create multiple projects rapidly
        for i in range(6):  # Limit is 5 per minute
            response = client.post(
                "/v1/projects",
                json={"name": f"Rate Test {i}"},
                headers={"X-ODIN-Agent": "did:odin:test"}
            )
            if i < 5:
                assert response.status_code == 200
            else:
                assert response.status_code == 429
                assert "Rate limit exceeded" in response.json()["detail"]
    
    def test_create_byok_token_success(self):
        """Test BYOK token creation."""
        response = client.post(
            "/v1/byok/token",
            json={
                "provider": "openai",
                "api_key": "sk-test123456789"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["token"].startswith("byok_")
        assert data["provider"] == "openai"
        assert "expires_at" in data
        return data["token"]
    
    def test_create_byok_token_invalid_key(self):
        """Test BYOK token creation with invalid key."""
        response = client.post(
            "/v1/byok/token",
            json={
                "provider": "openai",
                "api_key": "invalid-key"
            }
        )
        assert response.status_code == 400
        assert "Invalid OpenAI API key format" in response.json()["detail"]
    
    def test_create_experiment_success(self):
        """Test experiment creation."""
        project_id = self.test_create_project_success()
        
        response = client.post(
            "/v1/experiments",
            json={
                "id": "test-experiment",
                "variant": "A",
                "goal": "Test model comparison",
                "rollout_pct": 10
            },
            headers={"X-ODIN-Project-ID": project_id}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "created"
        assert data["experiment_id"] == "test-experiment"
    
    def test_upload_dataset_success(self):
        """Test dataset upload."""
        project_id = self.test_create_project_success()
        
        # Create test CSV content
        csv_content = "name,email,role\nJohn,john@test.com,Engineer\nJane,jane@test.com,Manager"
        
        response = client.post(
            "/v1/datasets",
            files={"file": ("test.csv", csv_content, "text/csv")},
            headers={"X-ODIN-Project-ID": project_id}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"].startswith("ds_")
        assert data["project_id"] == project_id
        assert data["name"] == "test.csv"
        assert data["format"] == "csv"
        assert data["record_count"] == 2
        return data["id"]
    
    def test_upload_dataset_too_large(self):
        """Test dataset upload size limit."""
        project_id = self.test_create_project_success()
        
        # Create file that's too large (>10MB)
        large_content = "x" * (11 * 1024 * 1024)
        
        response = client.post(
            "/v1/datasets",
            files={"file": ("large.json", large_content, "application/json")},
            headers={"X-ODIN-Project-ID": project_id}
        )
        assert response.status_code == 413
        assert "File too large" in response.json()["detail"]
    
    def test_create_run_success(self):
        """Test experiment run creation."""
        project_id = self.test_create_project_success()
        dataset_id = self.test_upload_dataset_success()
        
        response = client.post(
            "/v1/runs",
            json={
                "experiment_id": "test-exp",
                "dataset_id": dataset_id,
                "realm": "business",
                "map_id": "iso20022_pain001_v1",
                "router_policy": "cost_optimized"
            },
            headers={"X-ODIN-Project-ID": project_id}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"].startswith("run_")
        assert data["status"] == "queued"
        return data["run_id"]
    
    def test_create_run_invalid_realm(self):
        """Test run creation with invalid realm for free tier."""
        project_id = self.test_create_project_success()
        dataset_id = self.test_upload_dataset_success()
        
        response = client.post(
            "/v1/runs",
            json={
                "dataset_id": dataset_id,
                "realm": "banking",  # Not allowed for free tier
                "map_id": "iso20022_pain001_v1"
            },
            headers={"X-ODIN-Project-ID": project_id}
        )
        assert response.status_code == 403
        assert "Free tier limited to business realm" in response.json()["detail"]
    
    @patch('asyncio.sleep', return_value=None)  # Speed up test
    def test_get_run_report_success(self, mock_sleep):
        """Test getting run report."""
        project_id = self.test_create_project_success()
        dataset_id = self.test_upload_dataset_success()
        run_id = self.test_create_run_success()
        
        # Wait a moment for background task to complete
        time.sleep(0.1)
        
        response = client.get(
            f"/v1/runs/{run_id}/report",
            headers={"X-ODIN-Project-ID": project_id}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert data["project_id"] == project_id
        assert data["dataset_id"] == dataset_id
        assert "metrics" in data
        assert "receipt_chain" in data
        
        # Check metrics structure
        metrics = data["metrics"]
        assert "coverage_pct" in metrics
        assert "p95_latency_ms" in metrics
        assert "cost_per_request" in metrics
        assert "success_rate" in metrics
    
    def test_export_receipts_success(self):
        """Test receipts export."""
        project_id = self.test_create_project_success()
        
        response = client.get(
            f"/v1/receipts/export?project_id={project_id}&format=ndjson"
        )
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert "media_type" in data
        assert "filename" in data
        assert data["media_type"] == "application/x-ndjson"
    
    def test_export_receipts_invalid_format(self):
        """Test receipts export with invalid format."""
        project_id = self.test_create_project_success()
        
        response = client.get(
            f"/v1/receipts/export?project_id={project_id}&format=xml"
        )
        assert response.status_code == 400
        assert "Supported formats: ndjson, parquet" in response.json()["detail"]


class TestHELPolicies:
    """Test HEL (HTTP Egress Limitation) policies."""
    
    def test_hel_policy_creation(self):
        """Test HEL policy creation and validation."""
        from gateway.middleware.hel_policy import HELPolicy, HELEnforcer
        
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
        assert error is None
        
        # Test missing header
        error = enforcer.validate_request({}, 512, "business")
        assert "Missing required header" in error
        
        # Test payload too large
        error = enforcer.validate_request(headers, 2048, "business")
        assert "Payload exceeds limit" in error
        
        # Test invalid realm
        error = enforcer.validate_request(headers, 512, "banking")
        assert "Realm not allowed" in error
    
    def test_hel_egress_validation(self):
        """Test egress URL validation."""
        from gateway.middleware.hel_policy import create_hel_enforcer
        
        enforcer = create_hel_enforcer()
        
        # Test blocked domains
        error = enforcer.validate_egress_url("http://localhost:8080/api")
        assert "Domain blocked" in error
        
        error = enforcer.validate_egress_url("http://127.0.0.1/metadata")
        assert "Domain blocked" in error
        
        error = enforcer.validate_egress_url("http://metadata.google.internal/")
        assert "Domain blocked" in error
        
        # Test allowed domain
        error = enforcer.validate_egress_url("https://api.openai.com/v1/chat")
        assert error is None
    
    def test_hel_header_redaction(self):
        """Test header redaction."""
        from gateway.middleware.hel_policy import create_hel_enforcer
        
        enforcer = create_hel_enforcer()
        
        headers = {
            "authorization": "Bearer secret-token",
            "x-api-key": "sk-secret123",
            "x-odin-byok-token": "byok_secret456",
            "user-agent": "ODIN/1.0",
            "content-type": "application/json"
        }
        
        redacted = enforcer.redact_headers(headers)
        
        assert redacted["authorization"] == "[REDACTED]"
        assert redacted["x-api-key"] == "[REDACTED]"
        assert redacted["x-odin-byok-token"] == "[REDACTED]"
        assert redacted["user-agent"] == "ODIN/1.0"
        assert redacted["content-type"] == "application/json"


class TestExperimentMiddleware:
    """Test experiment middleware functionality."""
    
    def test_experiment_variant_assignment(self):
        """Test deterministic experiment variant assignment."""
        from apps.gateway.middleware.experiment import get_experiment_variant
        
        # Test consistent assignment
        trace_id = "test-trace-123"
        experiment_id = "model-comparison"
        rollout_pct = 50
        
        variant1 = get_experiment_variant(trace_id, experiment_id, rollout_pct)
        variant2 = get_experiment_variant(trace_id, experiment_id, rollout_pct)
        
        assert variant1 == variant2  # Should be deterministic
        assert variant1 in ["A", "B"]
    
    def test_experiment_rollout_percentage(self):
        """Test experiment rollout percentage distribution."""
        from apps.gateway.middleware.experiment import get_experiment_variant
        
        experiment_id = "test-rollout"
        rollout_pct = 10  # 10% should get variant B
        
        # Test many trace IDs
        variants = []
        for i in range(1000):
            trace_id = f"trace-{i:04d}"
            variant = get_experiment_variant(trace_id, experiment_id, rollout_pct)
            variants.append(variant)
        
        b_count = variants.count("B")
        b_percentage = (b_count / len(variants)) * 100
        
        # Should be close to 10% (within 5% tolerance)
        assert 5 <= b_percentage <= 15
    
    def test_experiment_middleware_integration(self):
        """Test experiment middleware with kill-switch."""
        from apps.gateway.middleware.experiment import ExperimentMiddleware
        import os
        
        # Set kill-switch environment variable
        os.environ["ODIN_EXPERIMENT_KILL_SWITCH"] = "dangerous-experiment"
        
        try:
            middleware = ExperimentMiddleware()
            
            # Test blocked experiment
            headers = {"x-odin-experiment": "dangerous-experiment:B"}
            is_blocked = middleware.is_experiment_blocked("dangerous-experiment")
            assert is_blocked is True
            
            # Test allowed experiment
            is_blocked = middleware.is_experiment_blocked("safe-experiment")
            assert is_blocked is False
            
        finally:
            # Clean up
            if "ODIN_EXPERIMENT_KILL_SWITCH" in os.environ:
                del os.environ["ODIN_EXPERIMENT_KILL_SWITCH"]


class TestBenchRunner:
    """Test ODIN-Bench evaluation suite."""
    
    def test_bench_runner_creation(self):
        """Test BenchRunner initialization."""
        from bench.runner.run_bench import BenchRunner, BenchConfig
        
        config = BenchConfig(
            test_cases_dir="bench/cases",
            data_dir="bench/data",
            reports_dir="bench/reports"
        )
        
        runner = BenchRunner(config)
        assert runner.config == config
    
    def test_bench_translation_validation(self):
        """Test translation validation logic."""
        from bench.runner.run_bench import validate_translation_result
        
        # Test valid result
        input_data = {"amount": 1000, "currency": "EUR"}
        output_data = {
            "InstdAmt": {"Ccy": "EUR", "value": "1000.00"},
            "coverage_fields": ["InstdAmt"]
        }
        
        result = validate_translation_result(input_data, output_data)
        assert result["valid"] is True
        assert result["coverage_pct"] > 0
        assert result["enum_violations"] == 0
    
    def test_bench_property_validation(self):
        """Test property-based validation."""
        from bench.runner.run_bench import validate_iso20022_properties
        
        # Test valid ISO 20022 structure
        iso_data = {
            "GrpHdr": {"MsgId": "MSG123", "CreDtTm": "2024-01-01T12:00:00Z"},
            "PmtInf": [{"DbtrAcct": {"Id": {"IBAN": "DE89370400440532013000"}}}]
        }
        
        result = validate_iso20022_properties(iso_data)
        assert result["valid"] is True
        assert result["has_group_header"] is True
        assert result["has_payment_info"] is True


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
