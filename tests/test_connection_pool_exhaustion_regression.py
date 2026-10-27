import pytest
from sqlalchemy.pool import QueuePool

import payment.main as payment_module


class _DummyDBConnection:
    def close(self):
        pass

    def rollback(self):
        pass

    def cursor(self):
        return self

    def execute(self, *args, **kwargs):
        return None


def test_payment_pool_handles_more_concurrent_checkouts_than_legacy_limit():
    checked_out = []
    pool = QueuePool(
        creator=_DummyDBConnection,
        pool_size=payment_module.POOL_SIZE,
        max_overflow=payment_module.MAX_OVERFLOW,
        timeout=0.25,
    )

    try:
        # Unpatched defaults allow only 5 simultaneous checkouts.
        # The patched pool must support at least 10.
        for _ in range(10):
            checked_out.append(pool.connect())
        assert len(checked_out) == 10
    except Exception as exc:
        pytest.fail(
            f"Connection pool exhausted after {len(checked_out)} simultaneous "
            f"checkouts: {exc}"
        )
    finally:
        for connection in checked_out:
            connection.close()
        pool.dispose()
