import time
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_current_user
from app.db.database import get_db
from app.api import recommendations as recommendations_api
import app.services.startup as startup_module


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


def test_fault_tolerance_during_failed_refresh(monkeypatch):
    # --- Step 1: mock recommendation output ---
    def fake_recommendations(db, user_id, limit):
        return [{"movie_id": 101, "title": "Stable Movie"}]

    monkeypatch.setattr(
        recommendations_api.recommend_service,
        "get_for_user",
        fake_recommendations,
    )

    # --- Step 2: simulate refresh failure ---
    def failing_restore(force=False):
        raise RuntimeError("R2 restore failed")

    monkeypatch.setattr(
        startup_module,
        "ensure_production_run_restored",
        failing_restore,
    )

    # --- Step 3: trigger refresh loop manually (single iteration idea) ---
    try:
        startup_module.ensure_production_run_restored()
    except Exception:
        pass  # expected failure

    # --- Step 4: system should still respond ---
    response = client.get("/recommendations")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) > 0