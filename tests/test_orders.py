from unittest.mock import patch
import uuid
import httpx
import orders.main


def test_create_order_end_to_end(orders_client):
    unique_user = f"usr-{uuid.uuid4().hex[:8]}"
    item_id = "item-101"
    quantity = 2
    amount = 99.98
    idempotency_key = f"idemp-{uuid.uuid4().hex[:12]}"

    def mock_get(url, headers=None, **kwargs):
        req = httpx.Request("GET", url, headers=headers)
        if "/auth/verify" in url:
            return httpx.Response(200, json={"valid": True, "user_id": unique_user}, request=req)
        return httpx.Response(404, request=req)

    def mock_post(url, json=None, **kwargs):
        req = httpx.Request("POST", url)
        payload = json or {}
        if "/reserve" in url:
            return httpx.Response(
                200,
                json={
                    "reserved": True,
                    "item_id": item_id,
                    "quantity": payload.get("quantity", quantity),
                    "remaining_stock": 99998,
                },
                request=req,
            )
        if "/payment/charge" in url:
            return httpx.Response(
                200,
                json={
                    "payment_id": f"pay-{uuid.uuid4().hex[:12]}",
                    "order_id": payload.get("order_id"),
                    "amount": payload.get("amount", amount),
                    "status": "succeeded",
                    "idempotent_replay": False,
                },
                request=req,
            )
        return httpx.Response(404, request=req)

    with patch.object(orders.main.http_client, "get", side_effect=mock_get), \
         patch.object(orders.main.http_client, "post", side_effect=mock_post):
        response = orders_client.post(
            "/orders",
            json={
                "user_id": unique_user,
                "item_id": item_id,
                "quantity": quantity,
                "amount": amount,
                "idempotency_key": idempotency_key,
            },
            headers={"Authorization": "Bearer test-valid-token"},
        )

    assert response.status_code == 201
    created_order = response.json()
    assert created_order["order_id"].startswith("ord-")
    assert created_order["user_id"] == unique_user
    assert created_order["item_id"] == item_id
    assert created_order["quantity"] == quantity
    assert created_order["amount"] == amount
    assert created_order["status"] == "confirmed"
    assert created_order["created_at"] is not None

    # Verify order is persisted and retrievable via GET /orders/{order_id}
    fetch_resp = orders_client.get(f"/orders/{created_order['order_id']}")
    assert fetch_resp.status_code == 200
    fetched_order = fetch_resp.json()
    assert fetched_order["order_id"] == created_order["order_id"]
    assert fetched_order["user_id"] == unique_user
    assert fetched_order["status"] == "confirmed"


def test_create_order_auth_failure(orders_client):
    req = httpx.Request("GET", "http://auth/verify")
    with patch.object(orders.main.http_client, "get", return_value=httpx.Response(401, request=req)):
        response = orders_client.post(
            "/orders",
            json={"user_id": "usr-test", "item_id": "item-101", "quantity": 1, "amount": 49.99},
        )
    assert response.status_code == 401
    assert "Authentication failed" in response.json()["detail"]


def test_create_order_inventory_insufficient_stock(orders_client):
    get_req = httpx.Request("GET", "http://auth/verify")
    post_req = httpx.Request("POST", "http://inventory/reserve")

    with patch.object(orders.main.http_client, "get", return_value=httpx.Response(200, json={"valid": True}, request=get_req)), \
         patch.object(orders.main.http_client, "post", return_value=httpx.Response(409, request=post_req)):
        response = orders_client.post(
            "/orders",
            json={"user_id": "usr-test", "item_id": "item-101", "quantity": 999999, "amount": 49.99},
        )
    assert response.status_code == 409
    assert "Insufficient inventory stock" in response.json()["detail"]


def test_create_order_payment_failure(orders_client):
    get_req = httpx.Request("GET", "http://auth/verify")
    reserve_req = httpx.Request("POST", "http://inventory/reserve")
    pay_req = httpx.Request("POST", "http://payment/charge")

    def mock_post(url, **kwargs):
        if "/reserve" in url:
            return httpx.Response(200, json={"reserved": True}, request=reserve_req)
        if "/payment/charge" in url:
            return httpx.Response(500, request=pay_req)
        return httpx.Response(404, request=pay_req)

    with patch.object(orders.main.http_client, "get", return_value=httpx.Response(200, json={"valid": True}, request=get_req)), \
         patch.object(orders.main.http_client, "post", side_effect=mock_post):
        response = orders_client.post(
            "/orders",
            json={"user_id": "usr-test", "item_id": "item-101", "quantity": 1, "amount": 49.99},
        )
    assert response.status_code == 500
    assert "Payment charge failed" in response.json()["detail"]


def test_create_order_downstream_service_unreachable(orders_client):
    req = httpx.Request("GET", "http://auth/verify")
    with patch.object(orders.main.http_client, "get", side_effect=httpx.ConnectError("Network error", request=req)):
        response = orders_client.post(
            "/orders",
            json={"user_id": "usr-test", "item_id": "item-101", "quantity": 1, "amount": 49.99},
        )
    assert response.status_code == 503
    assert "Auth service unavailable" in response.json()["detail"]


def test_list_orders(orders_client):
    response = orders_client.get("/orders?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert "page" in data
    assert "page_size" in data
    assert "total" in data
    assert "orders" in data
    assert isinstance(data["orders"], list)
