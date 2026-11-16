import pytest
from sqlalchemy import select
import orders.main as orders_module

def test_connection_pool_capacity():
    # Verify that the engine is configured with a larger pool capacity (pool_size >= 20, max_overflow >= 30)
    assert orders_module.engine.pool.size() >= 20
    assert orders_module.engine.pool._max_overflow >= 30

    # Simulate checking out connections concurrently up to the new pool capacity without blocking/exhaustion
    connections = []
    try:
        for _ in range(25):
            conn = orders_module.engine.connect()
            connections.append(conn)
        
        # Verify we can execute a simple query on all checked-out connections
        for conn in connections:
            res = conn.execute(select(1)).scalar()
            assert res == 1
    finally:
        for conn in connections:
            conn.close()
