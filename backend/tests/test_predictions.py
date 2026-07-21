def test_list_predictions(client, auth_headers):
    response = client.get("/api/predictions/", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
