import pytest
from sqlalchemy.pool import QueuePool

import orders.main as orders_module


def test_connection_pool_capacity_for_health_check_burst():
    configured_pool = orders_module.engine.pool
    pool_size = configured_pool.size()
    max_overflow = configured_pool._max_overflow

    burst = 15
    test_pool = QueuePool(
        creator=lambda: object(),
        pool_size=pool_size,
        max_overflow=max_overflow,
        timeout=0.05,
    )
    checked_out = []
    try:
        for index in range(burst):
            try:
                checked_out.append(test_pool.connect())
            except Exception as exc:
                pytest.fail(
                    f'connection pool exhausted after {index} simultaneous checkouts; '
                    f'configured capacity is {pool_size + max_overflow}: {exc}'
                )
    finally:
        for connection in checked_out:
            connection.close()
        test_pool.dispose()
