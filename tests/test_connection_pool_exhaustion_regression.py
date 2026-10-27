import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.pool import QueuePool

import orders.main as orders_module


def test_connection_pool_capacity_handles_concurrent_checkouts():
    pool = orders_module.engine.pool
    configured_pool_size = pool.size()
    configured_max_overflow = getattr(pool, '_max_overflow', 0)

    test_engine = create_engine(
        'sqlite://',
        poolclass=QueuePool,
        pool_size=configured_pool_size,
        max_overflow=configured_max_overflow,
        pool_timeout=0.2,
        connect_args={'check_same_thread': False},
    )

    concurrency = 15
    release = threading.Event()
    condition = threading.Condition()
    attempted = 0
    acquired = 0
    timeout_errors = []
    unexpected_errors = []

    def checkout_worker():
        nonlocal attempted, acquired
        conn = None
        try:
            conn = test_engine.connect()
            with condition:
                acquired += 1
                attempted += 1
                condition.notify_all()
            release.wait(timeout=5.0)
        except PoolTimeoutError as exc:
            with condition:
                timeout_errors.append(exc)
                attempted += 1
                condition.notify_all()
        except Exception as exc:
            with condition:
                unexpected_errors.append(exc)
                attempted += 1
                condition.notify_all()
        finally:
            if conn is not None:
                conn.close()

    try:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(checkout_worker) for _ in range(concurrency)]
            with condition:
                while attempted < concurrency:
                    if not condition.wait(timeout=5.0):
                        break
            release.set()
            for future in futures:
                future.result(timeout=5.0)

        assert not unexpected_errors, f'Unexpected checkout errors: {unexpected_errors!r}'
        assert not timeout_errors, (
            f'Connection pool exhausted: {len(timeout_errors)} of {concurrency} concurrent '
            f'checkouts timed out with capacity {configured_pool_size + configured_max_overflow}'
        )
        assert acquired == concurrency
    finally:
        release.set()
        test_engine.dispose()
