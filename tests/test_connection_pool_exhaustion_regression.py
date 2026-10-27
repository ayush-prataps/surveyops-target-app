import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.pool import QueuePool

import payment.main as payment_module


def test_payment_pool_handles_burst_above_previous_capacity():
    burst = 10
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=QueuePool,
        pool_size=payment_module.POOL_SIZE,
        max_overflow=payment_module.MAX_OVERFLOW,
        pool_timeout=0.25,
    )

    release = threading.Event()
    condition = threading.Condition()
    acquired = 0
    errors = []

    def hold_connection(_):
        nonlocal acquired
        try:
            with engine.connect() as conn:
                with condition:
                    acquired += 1
                    condition.notify_all()
                release.wait(timeout=5.0)
                conn.execute(select(1))
        except Exception as exc:  # pragma: no cover - unpatched path
            with condition:
                errors.append(exc)
                condition.notify_all()

    try:
        with ThreadPoolExecutor(max_workers=burst) as executor:
            futures = [executor.submit(hold_connection, i) for i in range(burst)]
            with condition:
                completed = condition.wait_for(
                    lambda: acquired == burst or bool(errors),
                    timeout=2.0,
                )
                if not completed and not errors:
                    errors.append(AssertionError('Timed out waiting for concurrent checkouts'))
            release.set()
            for future in futures:
                future.result(timeout=5.0)

        assert not errors, f'Connection pool exhausted during {burst} concurrent checkouts: {errors!r}'
        assert acquired == burst
    finally:
        release.set()
        engine.dispose()
