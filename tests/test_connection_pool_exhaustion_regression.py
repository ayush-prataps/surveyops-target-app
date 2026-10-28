import concurrent.futures
from threading import Barrier, Event, Lock

from sqlalchemy.pool import QueuePool

import orders.main as orders_module


class FakeDBAPIConnection:
    def __init__(self):
        self.closed = False

    def rollback(self):
        pass

    def commit(self):
        pass

    def close(self):
        self.closed = True


def _pool_from_service_settings():
    service_pool = orders_module.engine.pool
    return QueuePool(
        creator=FakeDBAPIConnection,
        pool_size=service_pool.size(),
        max_overflow=service_pool._max_overflow,
        timeout=0.2,
        reset_on_return="rollback",
    )


def test_orders_pool_handles_concurrent_checkouts_above_legacy_capacity():
    pool = _pool_from_service_settings()
    n = 15
    barrier = Barrier(n)
    release = Event()
    attempted_event = Event()
    lock = Lock()
    acquired = []
    errors = []
    attempted = 0

    def worker():
        nonlocal attempted
        try:
            barrier.wait(timeout=2.0)
            conn = pool.connect()
            with lock:
                acquired.append(conn)
        except Exception as exc:
            with lock:
                errors.append(exc)
        finally:
            with lock:
                attempted += 1
                if attempted == n:
                    attempted_event.set()
            release.wait(timeout=2.0)

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=n)
    futures = []
    try:
        futures = [executor.submit(worker) for _ in range(n)]
        assert attempted_event.wait(timeout=3.0), "pool checkout attempts did not complete"
        release.set()
        for future in futures:
            future.result(timeout=3.0)

        assert not errors, f"connection pool exhausted under {n} concurrent checkouts: {errors!r}"
        assert len(acquired) == n
    finally:
        release.set()
        for conn in acquired:
            try:
                conn.close()
            except Exception:
                pass
        executor.shutdown(wait=True)
        pool.dispose()
