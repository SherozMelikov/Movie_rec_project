import time
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_current_user
from app.db.database import get_db
from app.api import recommendations as recommendations_api


class FakeUser:
    user_id = 1


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


def test_recommendation_response_time(monkeypatch):
    # Mock service to simulate realistic computation
    def fake_recommendations(db, user_id, limit):
        time.sleep(0.05)  # simulate 50ms processing
        return [
            {
                "movie_id": 101,
                "title": "Movie A",
                "genres": "Action",
                "poster_url": None,
                "release_date": None,
                "reason": "Test",
                "score": 0.9,
            }
        ]

    monkeypatch.setattr(
        recommendations_api.recommend_service,
        "get_for_user",
        fake_recommendations,
    )

    start = time.time()
    response = client.get("/recommendations")
    duration = (time.time() - start) * 1000  # ms

    assert response.status_code == 200

    # 🔥 PERFORMANCE ASSERTION
    assert duration < 500, f"Response too slow: {duration:.2f} ms"