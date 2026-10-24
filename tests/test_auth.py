def test_auth_login(auth_client):
    response = auth_client.post(
        "/auth/login",
        json={"username": "testuser", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert "user_id" in data
    assert data["token"].startswith("token-for-")


def test_auth_verify_success(auth_client):
    login_resp = auth_client.post(
        "/auth/login",
        json={"username": "alice", "password": "securepass"},
    )
    token = login_resp.json()["token"]

    response = auth_client.get(
        "/auth/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert "user_id" in data


def test_auth_verify_missing_header(auth_client):
    response = auth_client.get("/auth/verify")
    assert response.status_code == 401
    assert "Missing Authorization header" in response.json()["detail"]


def test_auth_verify_invalid_token(auth_client):
    response = auth_client.get(
        "/auth/verify",
        headers={"Authorization": "Bearer invalid"},
    )
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]
