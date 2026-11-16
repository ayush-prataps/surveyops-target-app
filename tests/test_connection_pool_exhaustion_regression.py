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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


class _FakePool:
    """A deterministic stand-in for SQLAlchemy's QueuePool.

    It models the configured capacity (pool_size + max_overflow) and the
    pool_timeout behavior. Checkouts beyond capacity block until timeout and
    then raise, exactly like the real pool.
    """

    def __init__(self, capacity, timeout):
        self.capacity = capacity
        self.timeout = timeout
        self._sem = threading.BoundedSemaphore(capacity)
        self._lock = threading.Lock()
        self.in_use = 0

    def connect(self):
        acquired = self._sem.acquire(timeout=self.timeout)
        if not acquired:
            raise TimeoutError("connection pool exhausted")
        with self._lock:
            self.in_use += 1
        return _FakeConnection()

    def release(self, conn):
        conn.close()
        with self._lock:
            self.in_use -= 1
        self._sem.release()


class _FakeEngine:
    def __init__(self, pool):
        self.pool = pool

    def connect(self):
        conn = self.pool.connect()
        return _ManagedConnection(self.pool, conn)


class _ManagedConnection:
    def __init__(self, pool, conn):
        self._pool = pool
        self._conn = conn

    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self._pool.release(self._conn)
        return False


def _engine_capacity(engine):
    """Derive capacity from the service module's configured engine."""
    pool = engine.pool
    pool_size = getattr(pool, "size", lambda: None)()
    max_overflow = getattr(pool, "_max_overflow", None)
    if pool_size is None or max_overflow is None:
        # Fall back to attributes on the engine's pool object.
        pool_size = getattr(pool, "_pool_size", None)
        max_overflow = getattr(pool, "_max_overflow", None)
    assert pool_size is not None, "could not determine pool_size from engine"
    assert max_overflow is not None, "could not determine max_overflow from engine"
    return pool_size + max_overflow


def _engine_timeout(engine):
    pool = engine.pool
    timeout = getattr(pool, "_timeout", None)
    if timeout is None:
        timeout = getattr(pool, "timeout", None)
    assert timeout is not None, "could not determine pool_timeout from engine"
    return float(timeout)


def test_health_endpoint_survives_concurrent_pool_usage(monkeypatch):
    """Concurrent /health probes must not exhaust the configured pool.

    The unpatched engine has capacity 10 (pool_size=5 + max_overflow=5).
    We hold 15 concurrent checkouts (above unpatched capacity, within the
    patched capacity of 40) and assert none time out.
    """
    capacity = _engine_capacity(orders_module.engine)
    timeout = _engine_timeout(orders_module.engine)

    # Sanity: patched capacity must exceed the unpatched capacity of 10.
    assert capacity > 10, f"pool capacity {capacity} not upgraded above 10"

    concurrent = 15
    assert concurrent <= capacity, (
        f"test requires capacity >= {concurrent}, got {capacity}"
    )

    fake_pool = _FakePool(capacity=capacity, timeout=timeout)
    fake_engine = _FakeEngine(fake_pool)
    monkeypatch.setattr(orders_module, "engine", fake_engine)

    results = []
    errors = []
    barrier = threading.Barrier(concurrent)

    def worker():
        try:
            barrier.wait(timeout=5)
            result = orders_module.health()
            results.append(result)
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(concurrent)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    try:
        assert not errors, f"health checks raised: {errors!r}"
        assert len(results) == concurrent
        for result in results:
            assert result.get("status") == "ok", result
    finally:
        # Ensure all fake connections are released.
        assert fake_pool.in_use == 0, f"leaked connections: {fake_pool.in_use}"
