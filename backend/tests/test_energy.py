def test_energy_summary(client, auth_headers):
    response = client.get("/api/energy/summary", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "total_records" in body
    assert "total_consumption_kwh" in body
    assert "average_consumption_kwh" in body
