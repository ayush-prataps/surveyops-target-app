import threading

import pytest
from sqlalchemy.pool import QueuePool

import payment.main as payment_module


class _DummyDBAPI:
    """Minimal DBAPI-like object so QueuePool can manage connections without a real driver."""

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def _creator():
    return _DummyDBAPI()


def test_pool_serves_concurrent_checkouts_above_base_pool_size():
    """
    Regression for connection_pool_exhaustion on /payment/charge.

    The service pool must be able to serve more concurrent checkouts than the
    base pool_size (via bounded overflow). With the unpatched config
    (max_overflow=0) the 6th concurrent checkout times out; with the patched
    config (max_overflow=10) all POOL_SIZE+5 checkouts succeed.
    """
    pool_size = payment_module.POOL_SIZE
    max_overflow = payment_module.MAX_OVERFLOW
    pool_timeout = payment_module.POOL_TIMEOUT

    # Sanity: the patched configuration must permit overflow beyond base size.
    assert max_overflow > 0, (
        "Pool must allow bounded overflow to avoid connection_pool_exhaustion"
    )

    concurrent_checkouts = pool_size + 5
    assert concurrent_checkouts <= pool_size + max_overflow, (
        "Test requires capacity for pool_size + 5 concurrent checkouts"
    )

    pool = QueuePool(
        creator=_creator,
        pool_size=pool_size,
        max_overflow=max_overflow,
        timeout=min(pool_timeout, 1.0),
        pre_ping=False,
    )

    acquired = []
    errors = []
    barrier = threading.Barrier(concurrent_checkouts)
    lock = threading.Lock()

    def checkout():
        try:
            barrier.wait(timeout=5.0)
            conn = pool.connect()
            with lock:
                acquired.append(conn)
        except Exception as exc:  # noqa: BLE001 - collect for assertion
            with lock:
                errors.append(exc)

    threads = [
        threading.Thread(target=checkout, daemon=True)
        for _ in range(concurrent_checkouts)
    ]

    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert not errors, (
            f"{len(errors)} concurrent checkouts failed (pool exhaustion): {errors!r}"
        )
        assert len(acquired) == concurrent_checkouts, (
            f"Expected {concurrent_checkouts} successful checkouts, got {len(acquired)}"
        )
    finally:
        for conn in acquired:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                pass
        pool.dispose()
