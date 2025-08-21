from fastapi.testclient import TestClient

def test_agent_beta_basic_metrics(monkeypatch):
    from apps.agent_beta import api as beta_api

    client = TestClient(beta_api.app)

    # health request should increment http metrics
    r = client.get("/health")
    assert r.status_code == 200

    m = client.get("/metrics").text
    assert "agent_beta_http_requests_total" in m
    assert "agent_beta_http_request_seconds_bucket" in m
