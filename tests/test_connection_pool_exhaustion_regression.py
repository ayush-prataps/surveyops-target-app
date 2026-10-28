import payment.main as payment_module
from sqlalchemy.pool import QueuePool


class _DummyDBAPIConnection:
    def close(self):
        pass


def test_pool_supports_concurrent_charge_checkouts():
    pool = QueuePool(
        creator=_DummyDBAPIConnection,
        pool_size=payment_module.POOL_SIZE,
        max_overflow=payment_module.MAX_OVERFLOW,
        timeout=0.2,
    )
    held = []
    try:
        for _ in range(10):
            held.append(pool.connect())
        assert len(held) == 10
    finally:
        for conn in held:
            conn.close()
        pool.dispose()
