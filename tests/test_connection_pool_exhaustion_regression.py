import threading
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

import orders.main as orders_module


# Number of concurrent checkouts to hold simultaneously.
# Unpatched capacity = pool_size(5) + max_overflow(5) = 10.
# Patched capacity   = pool_size(20) + max_overflow(20) = 40.
# 15 is above the unpatched ceiling and well within the patched ceiling.
CONCURRENT_CHECKOUTS = 15
CHECKOUT_TIMEOUT_SECONDS = 2.0


def _build_pool_from_module_config():
    """Build a QueuePool using the service module's configured engine parameters.

    We mirror the module's engine configuration (pool_size, max_overflow,
    pool_timeout) but use an in-memory SQLite URL so no real Postgres is needed.
    The pool sizing behavior is identical regardless of the underlying driver.
    """
    engine = orders_module.engine
    pool = engine.pool

    # Extract the configured pool parameters from the service's engine.
    pool_size = getattr(pool, "size", lambda: None)()
    max_overflow = getattr(pool, "_max_overflow", None)
    pool_timeout = getattr(pool, "_timeout", None)

    assert pool_size is not None, "Could not read pool_size from orders engine"
    assert max_overflow is not None, "Could not read max_overflow from orders engine"
    assert pool_timeout is not None, "Could not read pool_timeout from orders engine"

    # Build a test engine with the SAME pool sizing parameters as the service.
    test_engine = create_engine(
        "sqlite://",
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
    )
    return test_engine


def test_connection_pool_supports_concurrent_checkouts():
    """Regression: the orders DB pool must not exhaust under concurrent load.

    Holds CONCURRENT_CHECKOUTS connections simultaneously. On unpatched code
    the pool ceiling is 10, so the 11th+ checkout blocks until pool_timeout
    and raises TimeoutError. On patched code the ceiling is 40, so all 15
    checkouts succeed within the short timeout.
    """
    test_engine = _build_pool_from_module_config()
    acquired = []
    errors = []
    barrier = threading.Barrier(CONCURRENT_CHECKOUTS)
    lock = threading.Lock()

    def checkout():
        try:
            # Synchronize all threads so they attempt checkout simultaneously.
            barrier.wait(timeout=CHECKOUT_TIMEOUT_SECONDS)
            conn = test_engine.connect()
            with lock:
                acquired.append(conn)
        except Exception as exc:  # noqa: BLE001 - capture for assertion
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=checkout) for _ in range(CONCURRENT_CHECKOUTS)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=CHECKOUT_TIMEOUT_SECONDS + 1.0)

        # No thread should still be alive (i.e. blocked on pool checkout).
        alive = [t for t in threads if t.is_alive()]
        assert not alive, (
            f"{len(alive)} thread(s) blocked on pool checkout beyond timeout; "
            f"pool capacity is too small for {CONCURRENT_CHECKOUTS} concurrent checkouts"
        )

        # No checkout should have raised (e.g. sqlalchemy TimeoutError).
        assert not errors, (
            f"{len(errors)} concurrent checkout(s) failed with pool exhaustion: "
            f"{errors[0]!r}"
        )

        # All checkouts must have succeeded.
        assert len(acquired) == CONCURRENT_CHECKOUTS, (
            f"Expected {CONCURRENT_CHECKOUTS} successful checkouts, got {len(acquired)}"
        )
    finally:
        # Always release every acquired connection back to the pool.
        for conn in acquired:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                pass
        test_engine.dispose()
