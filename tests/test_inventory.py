def test_get_inventory_item(inventory_client):
    response = inventory_client.get("/inventory/item-101")
    assert response.status_code == 200
    data = response.json()
    assert data["item_id"] == "item-101"
    assert "stock" in data
    assert "price" in data


def test_get_inventory_item_not_found(inventory_client):
    response = inventory_client.get("/inventory/non-existent-item")
    assert response.status_code == 404
    assert response.json()["detail"] == "Item not found"


def test_reserve_stock_success(inventory_client):
    response = inventory_client.post("/inventory/item-101/reserve", json={"quantity": 1})
    assert response.status_code == 200
    data = response.json()
    assert data["reserved"] is True
    assert data["item_id"] == "item-101"
    assert data["quantity"] == 1
    assert data["remaining_stock"] >= 0


def test_reserve_stock_invalid_quantity(inventory_client):
    response = inventory_client.post("/inventory/item-101/reserve", json={"quantity": 0})
    assert response.status_code == 400
    assert "Quantity must be greater than zero" in response.json()["detail"]


def test_reserve_stock_insufficient(inventory_client):
    response = inventory_client.post("/inventory/item-101/reserve", json={"quantity": 9999999})
    assert response.status_code == 409
    assert "Insufficient stock" in response.json()["detail"]
