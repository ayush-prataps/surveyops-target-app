def test_auth_health(auth_client):
    response = auth_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert data.get("service") == "auth"


def test_inventory_health(inventory_client):
    response = inventory_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert data.get("service") == "inventory"
    assert data.get("db") == "connected"


def test_orders_health(orders_client):
    response = orders_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert data.get("service") == "orders"
    assert "downstream" in data
    assert "auth" in data["downstream"]
    assert "inventory" in data["downstream"]
    assert "payment" in data["downstream"]


def test_payment_health(payment_client):
    response = payment_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert data.get("service") == "payment"
    assert "db_host" in data
    assert "pool_size" in data
