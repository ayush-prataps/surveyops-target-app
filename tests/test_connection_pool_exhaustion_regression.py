import os

os.environ.pop("POOL_SIZE", None)
os.environ.pop("MAX_OVERFLOW", None)
os.environ["POOL_TIMEOUT"] = "0.2"

import payment.main as payment_module


def test_payment_pool_can_hold_concurrent_checkouts():
    # Unpatched defaults: pool_size=5, max_overflow=0, so the 6th checkout times out.
    # The patched defaults provide enough capacity for this concurrent burst.
    concurrent_checkouts = 8
    connections = []
    try:
        for _ in range(concurrent_checkouts):
            conn = payment_module.engine.connect()
            connections.append(conn)
            conn.execute(payment_module.select(1))
        assert len(connections) == concurrent_checkouts
    finally:
        for conn in connections:
            conn.close()
