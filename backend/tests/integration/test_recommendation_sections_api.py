

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.recommendations as recommendations_api


class FakeRecommendSectionsService:
    def get_sections_for_user(self, db, user_id, limit_per_section):
        return [
            {
                "title": "Top Picks for You",
                "subtitle": "Based on your activity",
                "items": [
                    {
                        "movie_id": 1,
                        "title": "Inception",
                        "genres": "Action|Sci-Fi",
                        "poster_url": None,
                        "release_date": None,
                        "reason": "Top pick",
                        "score": 0.95,
                    }
                ],
            },
            {
                "title": "Trending Now",
                "subtitle": "Popular right now",
                "items": [
                    {
                        "movie_id": 2,
                        "title": "Interstellar",
                        "genres": "Adventure|Sci-Fi",
                        "poster_url": None,
                        "release_date": None,
                        "reason": "Trending",
                        "score": 0.91,
                    }
                ],
            },
            {
                "title": "Because You Liked",
                "subtitle": "Similar to what you enjoyed",
                "items": [
                    {
                        "movie_id": 3,
                        "title": "The Matrix",
                        "genres": "Action|Sci-Fi",
                        "poster_url": None,
                        "release_date": None,
                        "reason": "Because you liked a similar movie",
                        "score": 0.89,
                    }
                ],
            },
            {
                "title": "Hidden Gems",
                "subtitle": "Great movies, less obvious",
                "items": [
                    {
                        "movie_id": 4,
                        "title": "Moon",
                        "genres": "Drama|Sci-Fi",
                        "poster_url": None,
                        "release_date": None,
                        "reason": "Hidden gem",
                        "score": 0.87,
                    }
                ],
            },
        ]


def test_get_recommendation_sections_returns_all_sections(monkeypatch):
    app = FastAPI()
    app.include_router(recommendations_api.router, prefix="/recommendations")

    fake_service = FakeRecommendSectionsService()
    monkeypatch.setattr(recommendations_api, "recommend_service", fake_service)

    def fake_get_db():
        yield object()

    app.dependency_overrides[recommendations_api.get_db] = fake_get_db
    app.dependency_overrides[recommendations_api.get_current_user] = lambda: SimpleNamespace(user_id=123)

    client = TestClient(app)

    response = client.get("/recommendations/sections", params={"limit_per_section": 6})

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 4

    assert data[0]["title"] == "Top Picks for You"
    assert data[1]["title"] == "Trending Now"
    assert data[2]["title"] == "Because You Liked"
    assert data[3]["title"] == "Hidden Gems"

    assert len(data[0]["items"]) == 1
    assert len(data[1]["items"]) == 1
    assert len(data[2]["items"]) == 1
    assert len(data[3]["items"]) == 1

    assert data[0]["items"][0]["title"] == "Inception"
    assert data[1]["items"][0]["title"] == "Interstellar"
    assert data[2]["items"][0]["title"] == "The Matrix"
    assert data[3]["items"][0]["title"] == "Moon"

    app.dependency_overrides.clear()