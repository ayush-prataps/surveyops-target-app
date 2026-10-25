import os

os.environ.pop("POOL_SIZE", None)
os.environ.pop("MAX_OVERFLOW", None)

import payment.main as payment_main


def test_connection_pool_has_sufficient_capacity_and_burst_headroom():
    assert payment_main.POOL_SIZE >= 15, (
        f"POOL_SIZE={payment_main.POOL_SIZE} is too small; expected >= 15"
    )
    assert payment_main.MAX_OVERFLOW >= 10, (
        f"MAX_OVERFLOW={payment_main.MAX_OVERFLOW} is too small; expected >= 10"
    )
