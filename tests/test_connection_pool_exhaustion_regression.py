import pytest
from sqlalchemy import pool
import orders.main as orders_module

def test_orders_connection_pool_capacity():
    """
    Verify that the orders service SQLAlchemy engine is configured with an expanded
    connection pool capacity (pool_size >= 20, max_overflow >= 30) to prevent
    connection pool exhaustion under concurrent load.
    """
    assert orders_module.engine.pool.size() >= 20, f"Expected pool_size to be at least 20, got {orders_module.engine.pool.size()}"
    assert isinstance(orders_module.engine.pool, pool.QueuePool), "Expected QueuePool for SQLAlchemy engine"
