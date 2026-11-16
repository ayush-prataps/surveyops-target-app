import concurrent.futures

import pytest

import payment.main as payment_module


def test_pool_handles_burst_above_base_pool_size():
    """
    Regression test for connection_pool_exhaustion on /payment/charge.

    The service configures an explicit QueuePool. With MAX_OVERFLOW=0 the pool
    can only serve POOL_SIZE concurrent checkouts; any additional concurrent
    request blocks until pool_timeout and then raises. This test holds
    POOL_SIZE + 5 concurrent checkouts (above unpatched capacity, within the
    patched capacity) with a short timeout and asserts none time out.
    """
    engine = payment_module.create_db_engine()
    base_size = payment_module.POOL_SIZE
    burst = base_size + 5

    # Ensure the test is meaningful: burst must exceed base pool size.
    assert burst > base_size

    # Use a short, deterministic pool timeout for the test engine so failures
    # surface quickly rather than waiting on the production timeout.
    engine.pool._timeout = 1.0

    acquired = []
    try:
        def checkout(_):
            conn = engine.connect()
            acquired.append(conn)
            return True

        with concurrent.futures.ThreadPoolExecutor(max_workers=burst) as pool:
            futures = [pool.submit(checkout, i) for i in range(burst)]
            results = [f.result(timeout=10) for f in futures]

        assert all(results), "All concurrent checkouts must succeed"
        assert len(acquired) == burst
    finally:
        for conn in acquired:
            try:
                conn.close()
            except Exception:
                pass
        engine.dispose()
