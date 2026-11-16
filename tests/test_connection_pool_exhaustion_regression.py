import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import orders.main as orders_module

def test_connection_pool_capacity():
    # Verify that the engine is configured with an adequate pool size and max overflow
    # to prevent connection pool exhaustion under concurrent load (pool_size >= 20, max_overflow >= 30).
    assert orders_module.engine.pool.size() >= 20
    assert orders_module.engine.pool._max_overflow >= 30

    # Simulate concurrent checkout capacity up to the configured pool size
    connections = []
    try:
        for _ in range(25):
            conn = orders_module.engine.connect()
            connections.append(conn)
        assert len(connections) == 25
    finally:
        for conn in connections:
            conn.close()
