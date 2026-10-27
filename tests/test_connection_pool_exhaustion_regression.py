import pytest
from sqlalchemy.pool import QueuePool

import payment.main as payment_module


class _DummyCursor:
    def close(self):
        pass

    def execute(self, *args, **kwargs):
        pass


class _DummyConnection:
    """Minimal DBAPI-like object so QueuePool can operate without a real database."""

    def rollback(self):
        pass

    def commit(self):
        pass

    def close(self):
        pass

    def cursor(self):
        return _DummyCursor()


def test_connection_pool_supports_concurrent_payment_checkouts_beyond_legacy_limit():
    # The unpatched service defaults to pool_size=5 and max_overflow=0.
    # This N exceeds the legacy capacity but is within the patched capacity.
    concurrent_checkouts = 10

    pool = QueuePool(
        creator=_DummyConnection,
        pool_size=payment_module.POOL_SIZE,
        max_overflow=payment_module.MAX_OVERFLOW,
        timeout=0.25,
    )

    held_connections = []
    try:
        for _ in range(concurrent_checkouts):
            held_connections.append(pool.connect())
    finally:
        for conn in held_connections:
            conn.close()
        pool.dispose()
