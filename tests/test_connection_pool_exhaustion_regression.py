import threading
import time

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

import payment.main as payment_module


def _build_pool_engine():
    """Build an engine using the service module's configured pool parameters."""
    return create_engine(
        "sqlite://",
        poolclass=QueuePool,
        pool_size=payment_module.POOL_SIZE,
        max_overflow=payment_module.MAX_OVERFLOW,
        pool_timeout=payment_module.POOL_TIMEOUT,
    )


def test_pool_absorbs_concurrent_burst_above_base_size():
    """
    Regression: with MAX_OVERFLOW=0 the pool capacity equals POOL_SIZE, so a
    burst of POOL_SIZE+1 concurrent checkouts blocks and times out. The fix
    must allow overflow so the burst succeeds within a short timeout.
    """
    engine = _build_pool_engine()
    base = payment_module.POOL_SIZE
    burst = base + 1
    # Use a short, deterministic timeout for the test regardless of prod config.
    engine.pool._timeout = 0.5

    acquired = []
    errors = []
    barrier = threading.Barrier(burst)

    def worker():
        try:
            barrier.wait(timeout=2.0)
            conn = engine.connect()
            acquired.append(conn)
            conn.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(burst)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert not errors, f"Concurrent checkouts failed: {errors!r}"
        assert len(acquired) == burst
    finally:
        for conn in acquired:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        engine.dispose()
