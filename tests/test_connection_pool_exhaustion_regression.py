import pytest
from sqlalchemy.pool import QueuePool

import payment.main as payment_module


class _DummyDBAPIConnection:
    # Minimal DBAPI connection stand-in for QueuePool checkout tests.
    def rollback(self):
        return None

    def close(self):
        return None

    def cursor(self):
        return None


def test_connection_pool_supports_concurrent_charge_checkouts():
    # Exceeds legacy capacity (5) but fits remediated capacity.
    required_connections = 10
    pool = QueuePool(
        creator=_DummyDBAPIConnection,
        pool_size=payment_module.POOL_SIZE,
        max_overflow=payment_module.MAX_OVERFLOW,
        timeout=0.25,
    )
    checked_out = []
    try:
        for _ in range(required_connections):
            checked_out.append(pool.connect())
        assert len(checked_out) == required_connections
    finally:
        for conn in checked_out:
            conn.close()
        pool.dispose()
