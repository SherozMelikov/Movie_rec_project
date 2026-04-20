from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_current_user
from app.db.database import get_db
from app.api import recommendations as recommendations_api
from app.api import movies as movies_api


class FakeUser:
    user_id = 1
    username = "testuser"
    email = "test@example.com"


class FakeDB:
    def close(self):
        pass


def override_get_current_user():
    return FakeUser()


def override_get_db():
    db = FakeDB()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


def setup_module(module):
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db


def teardown_module(module):
    app.dependency_overrides.clear()


def test_recommendations_endpoint_responds(monkeypatch):
    monkeypatch.setattr(
        recommendations_api.recommend_service,
        "get_for_user",
        lambda db, user_id, limit: [
            {
                "movie_id": 101,
                "title": "Movie A",
                "genres": "Action",
                "poster_url": None,
                "release_date": None,
                "reason": "Based on collaborative patterns",
                "score": 0.95,
            }
        ],
    )

    response = client.get("/recommendations")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["movie_id"] == 101
    assert "title" in data[0]
    assert "score" in data[0]


def test_recommendation_sections_endpoint_responds(monkeypatch):
    monkeypatch.setattr(
        recommendations_api.recommend_service,
        "get_sections_for_user",
        lambda db, user_id, limit_per_section: [
            {
                "title": "Top Picks for You",
                "subtitle": "Based on your activity",
                "items": [
                    {
                        "movie_id": 101,
                        "title": "Movie A",
                        "genres": "Action",
                        "poster_url": None,
                        "release_date": None,
                        "reason": "Based on collaborative patterns",
                        "score": 0.95,
                    }
                ],
            }
        ],
    )

    response = client.get("/recommendations/sections")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["title"] == "Top Picks for You"
    assert isinstance(data[0]["items"], list)
    assert data[0]["items"][0]["movie_id"] == 101


def test_movies_browse_endpoint_responds(monkeypatch):
    monkeypatch.setattr(
        movies_api.movie_service,
        "browse_movies",
        lambda db, title=None, genre=None, limit=20: [
            {
                "movie_id": 201,
                "title": "Movie B",
                "genres": "Drama",
                "poster_url": None,
                "overview": None,
                "release_date": None,
            }
        ],
    )

    response = client.get("/movies/browse")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["movie_id"] == 201
    assert data[0]["title"] == "Movie B"


def test_movies_genres_endpoint_responds(monkeypatch):
    monkeypatch.setattr(
        movies_api.movie_service,
        "list_genres",
        lambda db: ["Action", "Drama", "Comedy"],
    )

    response = client.get("/movies/genres")

    assert response.status_code == 200
    data = response.json()
    assert data == ["Action", "Drama", "Comedy"]