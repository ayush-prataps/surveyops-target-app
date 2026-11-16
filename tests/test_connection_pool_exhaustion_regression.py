import threading
import time

import pytest

import orders.main as orders_module


class _FakeConnection:
    def __init__(self):
        self.closed = False

    def execute(self, *args, **kwargs):
        return None

    def close(self):
        self.closed = True


class _FakePool:
    """A deterministic stand-in for the SQLAlchemy QueuePool that enforces
    the configured capacity and timeout semantics."""

    def __init__(self, capacity: int, timeout: float):
        self.capacity = capacity
        self.timeout = timeout
        self._sem = threading.BoundedSemaphore(capacity)
        self._lock = threading.Lock()
        self._checked_out = 0

    def acquire(self):
        acquired = self._sem.acquire(timeout=self.timeout)
        if not acquired:
            raise TimeoutError("connection pool exhausted")
        with self._lock:
            self._checked_out += 1
        return _FakeConnection()

    def release(self, conn):
        conn.close()
        with self._lock:
            self._checked_out -= 1
        self._sem.release()


class _FakeEngine:
    def __init__(self, pool: _FakePool):
        self.pool = pool

    def connect(self):
        return _FakeEngineContext(self.pool)


class _FakeEngineContext:
    def __init__(self, pool: _FakePool):
        self.pool = pool
        self.conn = None

    def __enter__(self):
        self.conn = self.pool.acquire()
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if self.conn is not None:
            self.pool.release(self.conn)
            self.conn = None
        return False


def _configured_capacity() -> int:
    """Derive total pool capacity from the service module's engine config."""
    pool = orders_module.engine.pool
    size = getattr(pool, "size", lambda: 5)()
    overflow = getattr(pool, "_max_overflow", 5)
    return size + overflow


def _configured_timeout() -> float:
    pool = orders_module.engine.pool
    timeout = getattr(pool, "_timeout", 30.0)
    # Keep the test deterministic and fast regardless of production timeout.
    return min(float(timeout), 2.0)


def test_health_endpoint_survives_concurrent_pool_usage(monkeypatch):
    """Fire more concurrent /health calls than the unpatched pool capacity.

    Unpatched capacity is 10 (pool_size=5 + max_overflow=5). We issue 15
    concurrent health checks. With the unpatched config, at least one
    acquire will time out and the health handler will return 'degraded'.
    With the patched config (capacity 40), all succeed.
    """
    capacity = _configured_capacity()
    timeout = _configured_timeout()

    # Concurrency chosen to exceed the unpatched capacity (10) but stay
    # within the patched capacity (40).
    concurrency = 15
    assert concurrency > 10, "test must exceed unpatched capacity"
    assert concurrency <= capacity, (
        f"patched capacity {capacity} must accommodate {concurrency} concurrent checks"
    )

    fake_pool = _FakePool(capacity=capacity, timeout=timeout)
    fake_engine = _FakeEngine(fake_pool)
    monkeypatch.setattr(orders_module, "engine", fake_engine)

    results = []
    errors = []
    barrier = threading.Barrier(concurrency)

    def worker():
        try:
            barrier.wait(timeout=5)
            results.append(orders_module.health())
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(concurrency)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
    finally:
        for t in threads:
            if t.is_alive():
                t.join(timeout=1)

    assert not errors, f"unexpected errors during concurrent health checks: {errors}"
    assert len(results) == concurrency
    degraded = [r for r in results if r.get("status") != "ok"]
    assert not degraded, (
        f"{len(degraded)}/{concurrency} health checks degraded due to pool exhaustion: {degraded}"
    )
