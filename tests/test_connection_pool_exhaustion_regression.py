import pytest
from sqlalchemy import select
import payment.main as payment_module

def test_connection_pool_capacity_regression():
    """
    Deterministic regression test for connection pool exhaustion (SM-014).
    Verifies that the database engine pool capacity can support concurrent
    checkouts above the old default (5) without exhaustion/timeout under burst load.
    """
    # Ensure the engine is created with the updated default pool configuration
    engine = payment_module.create_db_engine()
    
    # Number of concurrent connections to hold, exceeding the old pool size of 5
    concurrency_count = 10
    connections = []
    
    try:
        # Simultaneously check out concurrency_count connections
        for _ in range(concurrency_count):
            conn = engine.connect()
            connections.append(conn)
            # Perform a lightweight operation to ensure connection is active and usable
            conn.execute(select(1))
            
        # If we successfully acquire concurrency_count connections without pool timeout,
        # the pool capacity and overflow are sufficient.
        assert len(connections) == concurrency_count
    finally:
        for conn in connections:
            try:
                conn.close()
            except Exception:
                pass
        engine.dispose()
