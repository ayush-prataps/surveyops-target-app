import pytest
from sqlalchemy import select
import orders.main as orders_module

def test_connection_pool_capacity():
    """Verify that the database engine pool configuration supports concurrency above the old default (5+5=10)."""
    # The patched engine has pool_size=20 and max_overflow=30 (total capacity 50).
    # We test acquiring 12 concurrent connections, which would exhaust the old pool size of 10.
    engine = orders_module.engine
    connections = []
    try:
        for _ in range(12):
            conn = engine.connect()
            connections.append(conn)
        
        # Verify connections are active and functional
        for conn in connections:
            res = conn.execute(select(1)).scalar()
            assert res == 1
    finally:
        for conn in connections:
            conn.close()
