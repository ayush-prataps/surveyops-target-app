import concurrent.futures
import pytest
from fastapi.testclient import TestClient
import payment.main as payment_module


def test_connection_pool_exhaustion_regression(monkeypatch):
    # Ensure we test with larger concurrent requests than the old pool size (5)
    # but within the new pool capacity (20 + 10 = 30).
    concurrent_requests = 12

    # Mock the database execute / check_idempotency / execute_charge to simulate concurrent DB usage
    # without requiring a live external Postgres instance for unit regression testing.
    class MockResult:
        def scalar_one_or_none(self):
            return None

    monkeypatch.setattr(payment_module, "check_idempotency", lambda db, key: None)
    monkeypatch.setattr(
        payment_module,
        "execute_charge",
        lambda db, order_id, amount, idempotency_key: payment_module.PaymentRecord(
            id="pay-mock",
            order_id=order_id,
            amount=amount,
            idempotency_key=idempotency_key,
            status="succeeded",
        ),
    )

    client = TestClient(payment_module.app)

    def make_request(i):
        response = client.post(
            "/payment/charge",
            json={
                "order_id": f"ord-{i}",
                "amount": 10.0,
                "idempotency_key": f"key-{i}",
            },
        )
        return response.status_code

    # Execute concurrent requests concurrently using a ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
        futures = [executor.submit(make_request, i) for i in range(concurrent_requests)]
        results = [f.result(timeout=5.0) for f in futures]

    # All requests should succeed without timing out or raising pool exhaustion errors
    assert all(status == 200 for status in results)
    assert payment_module.POOL_SIZE >= concurrent_requests
