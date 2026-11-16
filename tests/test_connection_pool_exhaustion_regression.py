import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
import orders.main as orders_module


def test_health_endpoint_connection_pool_usage(monkeypatch):
    # Mock the session execution to verify health endpoint uses SessionLocal/pooled context cleanly
    executed = []

    class MockSession:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def execute(self, stmt):
            executed.append(True)

    monkeypatch.setattr(orders_module, "SessionLocal", MockSession)

    client = TestClient(orders_module.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert len(executed) > 0
