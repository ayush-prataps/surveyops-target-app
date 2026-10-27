from sqlalchemy.pool import QueuePool

import payment.main as payment_module


class _DummyDBAPIConnection:
    def close(self):
        pass

    def rollback(self):
        pass

    def commit(self):
        pass


def test_connection_pool_supports_concurrent_charge_connections():
    pool = QueuePool(
        creator=_DummyDBAPIConnection,
        pool_size=payment_module.POOL_SIZE,
        max_overflow=payment_module.MAX_OVERFLOW,
        timeout=0.2,
    )
    checked_out = []
    try:
        for _ in range(8):
            checked_out.append(pool.connect())
        assert len(checked_out) == 8
    finally:
        for connection in checked_out:
            connection.close()
        pool.dispose()
