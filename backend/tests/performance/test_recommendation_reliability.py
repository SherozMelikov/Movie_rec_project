import time
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_current_user
from app.db.database import get_db
from app.api import recommendations as recommendations_api


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


def test_recommendation_reliability_under_repeated_requests(monkeypatch):
    def fake_recommendations(db, user_id, limit):
        return [
            {
                "movie_id": 101,
                "title": "Movie A",
                "genres": "Action",
                "poster_url": None,
                "release_date": None,
                "reason": "Test recommendation",
                "score": 0.9,
            }
        ]

    monkeypatch.setattr(
        recommendations_api.recommend_service,
        "get_for_user",
        fake_recommendations,
    )

    num_requests = 300
    failures = []

    for i in range(num_requests):
        try:
            response = client.get("/recommendations")

            if response.status_code != 200:
                failures.append(f"Request {i} failed with status {response.status_code}")
                continue

            data = response.json()
            if not isinstance(data, list):
                failures.append(f"Request {i} returned invalid format")
                continue

            if len(data) > 0:
                item = data[0]
                if "movie_id" not in item or "title" not in item:
                    failures.append(f"Request {i} returned invalid item structure")

        except Exception as e:
            failures.append(f"Request {i} raised exception: {str(e)}")

        time.sleep(0.01)

    assert not failures, f"Failures detected: {failures}"