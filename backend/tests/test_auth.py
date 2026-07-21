def test_health_check(client):
    response = client.get("/api/system/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "database" in body


def test_register_and_login(client):
    email = "authuser@example.com"
    password = "securepass123"

    register_response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password},
    )
    assert register_response.status_code == 201
    assert register_response.json()["email"] == email

    login_response = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()
