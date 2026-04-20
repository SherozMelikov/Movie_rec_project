from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_recommendations_requires_auth():
    response = client.get("/recommendations")

    assert response.status_code == 401


def test_recommendations_with_invalid_token_rejected():
    response = client.get(
        "/recommendations",
        headers={"Authorization": "Bearer invalid_token"}
    )

    assert response.status_code == 401