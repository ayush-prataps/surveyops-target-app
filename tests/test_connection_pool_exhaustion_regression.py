from sqlalchemy.pool import QueuePool

import payment.main as payment_module


class _FakeDBAPIConnection:
    def close(self):
        pass

    def rollback(self):
        pass

    def cursor(self):
        return None


def test_payment_pool_allows_concurrent_charge_connections():
    required_concurrent_connections = 10
    pool = QueuePool(
        creator=_FakeDBAPIConnection,
        pool_size=payment_module.POOL_SIZE,
        max_overflow=payment_module.MAX_OVERFLOW,
        timeout=0.2,
    )

    acquired = []
    try:
        for _ in range(required_concurrent_connections):
            acquired.append(pool.connect())
    finally:
        for connection in acquired:
            connection.close()
        pool.dispose()
