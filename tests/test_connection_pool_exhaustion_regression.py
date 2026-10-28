import concurrent.futures
import threading

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

import payment.main as payment_module


def test_payment_pool_supports_concurrent_checkouts_without_timeout():
    concurrency = 10
    pool_timeout = 0.2
    barrier_timeout = 2.0

    engine = create_engine(
        'sqlite://',
        poolclass=QueuePool,
        pool_size=payment_module.POOL_SIZE,
        max_overflow=payment_module.MAX_OVERFLOW,
        pool_timeout=pool_timeout,
    )
    barrier = threading.Barrier(concurrency)
    acquired = []
    errors = []

    def hold_connection(worker_id):
        conn = None
        try:
            conn = engine.connect()
            barrier.wait(timeout=barrier_timeout)
            conn.execute(text('SELECT 1'))
            acquired.append(worker_id)
        except Exception as exc:
            errors.append(exc)
        finally:
            if conn is not None:
                conn.close()

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(hold_connection, i) for i in range(concurrency)]
            for future in futures:
                future.result(timeout=barrier_timeout + 2.0)
    finally:
        engine.dispose()

    assert not errors, f'Concurrent checkout(s) timed out/failed: {errors!r}'
    assert len(acquired) == concurrency
