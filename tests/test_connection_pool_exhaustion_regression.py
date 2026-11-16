import pytest
from sqlalchemy.pool import QueuePool
import payment.main as payment_module

def test_connection_pool_capacity_regression():
    """
    Deterministic regression test for connection pool exhaustion (inc-7964cb84).
    Verifies that the configured pool size and max overflow are sufficient to handle
    concurrent connections above the old limit of 5 (e.g. 10 concurrent checkouts)
    without exhausting the pool and timing out.
    """
    # Ensure the upgraded pool settings are active
    assert payment_module.POOL_SIZE >= 20
    assert payment_module.POOL_SIZE + payment_module.MAX_OVERFLOW >= 30

    engine = payment_module.engine
    assert isinstance(engine.pool, QueuePool)

    connections = []
    try:
        # Acquire 10 concurrent connections (which exceeds the old limit of 5 without overflow)
        for _ in range(10):
            conn = engine.connect()
            connections.append(conn)
        
        # If we successfully acquire 10 concurrent connections, the pool capacity is adequate
        assert len(connections) == 10
    finally:
        for conn in connections:
            conn.close()
