import pytest
from sqlalchemy.exc import TimeoutError as SATimeoutError
import payment.main as payment_module

def test_connection_pool_capacity_regression():
    """
    Regression test for connection pool exhaustion (SM-014).
    Verifies that the database engine's pool size and max overflow are configured
    to handle concurrent checkouts exceeding the old default limit of 5 without timing out.
    """
    engine = payment_module.engine
    pool = engine.pool
    
    # Ensure the capacity is at least 15 (old limit was 5 + 0 overflow = 5)
    total_capacity = payment_module.POOL_SIZE + payment_module.MAX_OVERFLOW
    assert total_capacity >= 15, f"Pool capacity {total_capacity} is too low and prone to exhaustion."

    connections = []
    try:
        # Attempt to check out 10 concurrent connections (which exceeds the old limit of 5)
        for _ in range(10):
            conn = engine.connect()
            connections.append(conn)
        assert len(connections) == 10
    finally:
        for conn in connections:
            conn.close()
