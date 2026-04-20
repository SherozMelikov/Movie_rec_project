# pytest  tests/integration/test_similar_movies_api.py
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.movies as movies_api


class FakeMovieService:
    def similar_movies(self, db, movie_id, k):
        return [
            {
                "movie_id": 2,
                "title": "Interstellar",
                "genres": "Adventure|Sci-Fi",
                "poster_url": None,
                "overview": None,
                "release_date": None,
            },
            {
                "movie_id": 3,
                "title": "The Matrix",
                "genres": "Action|Sci-Fi",
                "poster_url": None,
                "overview": None,
                "release_date": None,
            },
        ]


def test_similar_movies_returns_results(monkeypatch):
    app = FastAPI()
    app.include_router(movies_api.router, prefix="/movies")

    fake_service = FakeMovieService()
    monkeypatch.setattr(movies_api, "movie_service", fake_service)

    def fake_get_db():
        yield object()

    app.dependency_overrides[movies_api.get_db] = fake_get_db

    client = TestClient(app)

    response = client.get("/movies/1/similar", params={"k": 2})

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["title"] == "Interstellar"
    assert data[1]["title"] == "The Matrix"

    app.dependency_overrides.clear()