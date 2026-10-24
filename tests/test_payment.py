import uuid


def test_payment_charge_and_idempotency(payment_client):
    idempotency_key = f"idemp-test-{uuid.uuid4().hex}"
    order_id = f"ord-{uuid.uuid4().hex[:12]}"
    amount = 49.99

    payload = {
        "order_id": order_id,
        "amount": amount,
        "idempotency_key": idempotency_key,
    }

    # First charge request
    first_resp = payment_client.post("/payment/charge", json=payload)
    assert first_resp.status_code == 200
    first_data = first_resp.json()
    assert first_data["status"] == "succeeded"
    assert first_data["order_id"] == order_id
    assert first_data["amount"] == amount
    assert first_data["idempotent_replay"] is False
    payment_id = first_data["payment_id"]
    assert payment_id.startswith("pay-")

    # Repeat charge request with the identical idempotency key
    second_resp = payment_client.post("/payment/charge", json=payload)
    assert second_resp.status_code == 200
    second_data = second_resp.json()
    assert second_data["status"] == "succeeded"
    assert second_data["order_id"] == order_id
    assert second_data["amount"] == amount
    assert second_data["idempotent_replay"] is True
    # Verify that repeat call returns the same payment ID
    assert second_data["payment_id"] == payment_id


def test_payment_charge_invalid_amount(payment_client):
    response = payment_client.post(
        "/payment/charge",
        json={
            "order_id": f"ord-{uuid.uuid4().hex[:12]}",
            "amount": -5.00,
            "idempotency_key": f"idemp-test-{uuid.uuid4().hex}",
        },
    )
    assert response.status_code == 400
    assert "Payment amount must be positive" in response.json()["detail"]
