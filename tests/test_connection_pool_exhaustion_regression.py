import pytest
from fastapi.testclient import TestClient
import payment.main as payment_module

def test_connection_pool_exhaustion_regression():
    # Assert that configured pool size and overflow support at least 8 concurrent checkouts without exhaustion
    assert payment_module.POOL_SIZE >= 20 or (payment_module.POOL_SIZE + payment_module.MAX_OVERFLOW) >= 8

    # Simulate high concurrency checkout stress test against the engine connection pool
    connections = []
    try:
        for _ in range(8):
            conn = payment_module.engine.connect()
            connections.append(conn)
    finally:
        for conn in connections:
            conn.close()
