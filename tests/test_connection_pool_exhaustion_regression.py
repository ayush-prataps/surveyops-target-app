import threading
import time

import httpx
import pytest

import orders.main as orders_module


class _SlowTransport(httpx.BaseTransport):
    """Transport that holds each connection briefly to simulate slow downstreams."""

    def __init__(self, hold_seconds: float = 0.05):
        self.hold_seconds = hold_seconds
        self._lock = threading.Lock()
        self.in_flight = 0
        self.max_in_flight = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        with self._lock:
            self.in_flight += 1
            if self.in_flight > self.max_in_flight:
                self.max_in_flight = self.in_flight
        try:
            time.sleep(self.hold_seconds)
            return httpx.Response(200, json={"ok": True})
        finally:
            with self._lock:
                self.in_flight -= 1


def test_orders_http_client_pool_does_not_exhaust_under_concurrency():
    """
    Regression test for connection_pool_exhaustion on /orders.

    The unpatched client uses httpx defaults (max_connections=100) but with a
    10s timeout and no explicit pool timeout, so under a burst of concurrent
    downstream calls the pool can be exhausted and requests hang until the
    read timeout fires. The patched client configures explicit pool limits and
    a short pool-acquisition timeout, so concurrent requests complete quickly
    without timing out.

    We drive the service's configured client directly (not via importlib) so
    Prometheus metrics are registered exactly once.
    """
    client = orders_module.http_client
    assert isinstance(client, httpx.Client)

    # Swap in a slow transport to simulate downstream latency while keeping
    # the client's configured pool limits/timeouts intact.
    original_transport = client._transport
    slow_transport = _SlowTransport(hold_seconds=0.05)
    client._transport = slow_transport

    # Concurrency chosen to exceed the unpatched effective capacity under the
    # 10s timeout while staying within the patched pool (max_connections=50).
    concurrency = 40
    results: list[tuple[int, float]] = []
    results_lock = threading.Lock()
    barrier = threading.Barrier(concurrency)

    def worker() -> None:
        try:
            barrier.wait(timeout=5.0)
            start = time.perf_counter()
            try:
                resp = client.get("http://downstream.test/ping")
                elapsed = time.perf_counter() - start
                with results_lock:
                    results.append((resp.status_code, elapsed))
            except httpx.TimeoutException:
                elapsed = time.perf_counter() - start
                with results_lock:
                    results.append((-1, elapsed))
        finally:
            pass

    threads = [threading.Thread(target=worker) for _ in range(concurrency)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15.0)
    finally:
        # Restore the original transport and close any lingering state.
        client._transport = original_transport

    assert len(results) == concurrency, (
        f"Only {len(results)}/{concurrency} requests completed; "
        "connection pool likely exhausted"
    )

    timeouts = [r for r in results if r[0] == -1]
    assert not timeouts, (
        f"{len(timeouts)} requests timed out due to connection pool exhaustion: "
        f"{timeouts[:5]}"
    )

    # All requests should have succeeded and completed well under the pool
    # timeout, proving the pool was not exhausted.
    assert all(status == 200 for status, _ in results)
    max_elapsed = max(elapsed for _, elapsed in results)
    assert max_elapsed < 5.0, (
        f"Slowest request took {max_elapsed:.2f}s, indicating pool contention"
    )
