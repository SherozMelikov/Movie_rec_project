##pytest tests/integration/test_recommendations_api.py -v

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.recommendations as recommendations_api


class FakeRecommendService:
    def get_for_user(self, db, user_id, limit):
        return [
            {
                "movie_id": 1,
                "title": "Inception",
                "genres": "Action|Sci-Fi",
                "poster_url": None,
                "release_date": None,
                "reason": "Because you liked similar movies",
                "score": 0.95,
            },
            {
                "movie_id": 2,
                "title": "Interstellar",
                "genres": "Adventure|Sci-Fi",
                "poster_url": None,
                "release_date": None,
                "reason": "Recommended for you",
                "score": 0.91,
            },
        ]


def test_get_recommendations_returns_items_and_calls_service(monkeypatch):
    app = FastAPI()
    app.include_router(recommendations_api.router, prefix="/recommendations")

    fake_service = FakeRecommendService()
    monkeypatch.setattr(recommendations_api, "recommend_service", fake_service)

    def fake_get_db():
        yield object()

    app.dependency_overrides[recommendations_api.get_db] = fake_get_db
    app.dependency_overrides[recommendations_api.get_current_user] = lambda: SimpleNamespace(user_id=123)

    client = TestClient(app)

    response = client.get("/recommendations", params={"limit": 10})

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["title"] == "Inception"
    assert data[1]["title"] == "Interstellar"

    app.dependency_overrides.clear()