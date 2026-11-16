import pytest
from sqlalchemy.pool import QueuePool

import payment.main as payment_module


class _DummyDBAPI:
    """Minimal DBAPI-like object so QueuePool can create connections without a real driver."""

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def _creator():
    return _DummyDBAPI()


def test_pool_capacity_supports_expected_concurrency():
    """
    Regression: /payment/charge exhausted the DB connection pool under moderate
    concurrency because the configured pool capacity was too small. Build a
    QueuePool using the service's configured parameters and hold N concurrent
    checkouts where N is above the old capacity (15) but within the new capacity.
    All checkouts must succeed without timing out.
    """
    pool_size = payment_module.POOL_SIZE
    max_overflow = payment_module.MAX_OVERFLOW
    pool_timeout = payment_module.POOL_TIMEOUT

    capacity = pool_size + max_overflow
    # Old capacity was 5 + 10 = 15. Require at least 20 concurrent connections.
    required_concurrency = 20
    assert capacity >= required_concurrency, (
        f"Configured pool capacity {capacity} (pool_size={pool_size}, "
        f"max_overflow={max_overflow}) is below required concurrency "
        f"{required_concurrency}; connection pool exhaustion will occur under load."
    )

    pool = QueuePool(
        creator=_creator,
        pool_size=pool_size,
        max_overflow=max_overflow,
        timeout=pool_timeout,
    )

    checked_out = []
    try:
        # Hold required_concurrency connections simultaneously with a short timeout.
        for _ in range(required_concurrency):
            conn = pool.connect()
            checked_out.append(conn)
        assert len(checked_out) == required_concurrency
    finally:
        for conn in checked_out:
            conn.close()
        pool.dispose()
