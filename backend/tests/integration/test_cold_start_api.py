from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.recommendations as recommendations_api


class FakeSeededColdStartRecommendService:
    def get_for_user(self, db, user_id, limit):
        return [
            {
                "movie_id": 201,
                "title": "Interstellar",
                "genres": "Adventure|Sci-Fi",
                "poster_url": None,
                "release_date": None,
                "reason": "Based on your onboarding selections",
                "score": 0.88,
            },
            {
                "movie_id": 202,
                "title": "The Matrix",
                "genres": "Action|Sci-Fi",
                "poster_url": None,
                "release_date": None,
                "reason": "Seeded cold-start recommendation",
                "score": 0.84,
            },
        ]


def test_seeded_cold_start_user_gets_recommendations(monkeypatch):
    app = FastAPI()
    app.include_router(recommendations_api.router, prefix="/recommendations")

    fake_service = FakeSeededColdStartRecommendService()
    monkeypatch.setattr(recommendations_api, "recommend_service", fake_service)

    def fake_get_db():
        yield object()

    app.dependency_overrides[recommendations_api.get_db] = fake_get_db
    app.dependency_overrides[recommendations_api.get_current_user] = lambda: SimpleNamespace(user_id=999)

    client = TestClient(app)

    response = client.get("/recommendations", params={"limit": 10})

    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["title"] == "Interstellar"
    assert data[1]["title"] == "The Matrix"

    app.dependency_overrides.clear()