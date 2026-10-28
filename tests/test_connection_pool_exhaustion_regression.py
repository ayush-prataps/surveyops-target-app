import threading
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
import orders.main as orders_module


def test_orders_connection_pool_capacity_allows_burst_concurrency():
    source_pool = orders_module.engine.pool
    pool_size = source_pool.size()
    max_overflow = source_pool._max_overflow

    burst = 15
    test_engine = create_engine(
        'sqlite://',
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=1.0,
        connect_args={'check_same_thread': False},
    )

    start = threading.Event()
    release = threading.Event()
    all_acquired = threading.Event()
    lock = threading.Lock()
    successful_checkouts = 0
    errors = []

    def worker():
        nonlocal successful_checkouts
        conn = None
        try:
            start.wait(timeout=2)
            conn = test_engine.connect()
            with lock:
                successful_checkouts += 1
                if successful_checkouts == burst:
                    all_acquired.set()
            release.wait(timeout=5)
        except Exception as exc:
            with lock:
                errors.append(exc)
        finally:
            if conn is not None:
                conn.close()

    threads = [threading.Thread(target=worker) for _ in range(burst)]
    try:
        for thread in threads:
            thread.start()
        start.set()
        acquired_all = all_acquired.wait(timeout=2)
        release.set()
        for thread in threads:
            thread.join(timeout=2)
    finally:
        release.set()
        test_engine.dispose()

    assert not errors, f'Concurrent connection checkout errors: {errors!r}'
    assert acquired_all and successful_checkouts == burst, (
        f'Only {successful_checkouts}/{burst} concurrent checkouts succeeded; '
        f'orders pool capacity is {pool_size + max_overflow}'
    )
