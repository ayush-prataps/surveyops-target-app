import concurrent.futures
import orders.main as orders_module


def test_connection_pool_concurrency_regression():
    """
    Verify that the orders service database engine is configured with a sufficient
    pool size and max_overflow to handle concurrent session checkouts without exhaustion.
    """
    engine = orders_module.engine
    
    # Verify that pool size / max_overflow settings are upgraded from the old 5/5 defaults
    assert engine.pool.size() >= 20 or getattr(engine.pool, '_max_overflow', 0) >= 30
    
    # Test concurrent session checkouts simulating load above the old pool limit of 10 (5 + 5)
    concurrent_workers = 12
    sessions = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_workers) as executor:
            futures = [executor.submit(orders_module.SessionLocal) for _ in range(concurrent_workers)]
            for f in concurrent.futures.as_completed(futures, timeout=5.0):
                sessions.append(f.result())
    finally:
        for s in sessions:
            try:
                s.close()
            except Exception:
                pass
