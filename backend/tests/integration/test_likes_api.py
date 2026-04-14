from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.likes as likes_api


class FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class FakeDB:
    def __init__(self, query_results):
        self._query_results = list(query_results)
        self.added = []
        self.deleted = []
        self.commit_count = 0

    def query(self, target):
        if not self._query_results:
            raise AssertionError(f"No fake query result left for target: {target}")
        return FakeQuery(self._query_results.pop(0))

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        self.commit_count += 1


def create_test_app(fake_db, *, override_auth: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(likes_api.router, prefix="/likes")

    def fake_get_db():
        yield fake_db

    app.dependency_overrides[likes_api.get_db] = fake_get_db

    if override_auth:
        app.dependency_overrides[likes_api.get_current_user] = lambda: SimpleNamespace(user_id=123)

    return app


def test_is_liked_returns_true():
    fake_db = FakeDB(query_results=[object()])
    app = create_test_app(fake_db)
    client = TestClient(app)

    response = client.get("/likes/10")

    assert response.status_code == 200
    assert response.json() == {"liked": True}

    app.dependency_overrides.clear()


def test_is_liked_returns_false():
    fake_db = FakeDB(query_results=[None])
    app = create_test_app(fake_db)
    client = TestClient(app)

    response = client.get("/likes/10")

    assert response.status_code == 200
    assert response.json() == {"liked": False}

    app.dependency_overrides.clear()


def test_like_movie_returns_404_when_movie_not_found():
    fake_db = FakeDB(query_results=[None])  # movie existence check
    app = create_test_app(fake_db)
    client = TestClient(app)

    response = client.post("/likes/55")

    assert response.status_code == 404
    assert response.json() == {"detail": "Movie not found"}
    assert fake_db.commit_count == 0
    assert fake_db.added == []

    app.dependency_overrides.clear()


def test_like_movie_is_idempotent_when_like_already_exists():
    fake_db = FakeDB(
        query_results=[
            object(),  # movie exists
            object(),  # existing like
        ]
    )
    app = create_test_app(fake_db)
    client = TestClient(app)

    response = client.post("/likes/55")

    assert response.status_code == 200
    assert response.json() == {"liked": True}
    assert fake_db.commit_count == 0
    assert fake_db.added == []

    app.dependency_overrides.clear()


def test_like_movie_creates_like_and_commits():
    fake_db = FakeDB(
        query_results=[
            object(),  # movie exists
            None,      # existing like not found
        ]
    )
    app = create_test_app(fake_db)
    client = TestClient(app)

    response = client.post("/likes/55")

    assert response.status_code == 200
    assert response.json() == {"liked": True}
    assert fake_db.commit_count == 1
    assert len(fake_db.added) == 1

    added_like = fake_db.added[0]
    assert added_like.user_id == 123
    assert added_like.movie_id == 55

    app.dependency_overrides.clear()


def test_unlike_movie_is_idempotent_when_like_missing():
    fake_db = FakeDB(query_results=[None])
    app = create_test_app(fake_db)
    client = TestClient(app)

    response = client.delete("/likes/55")

    assert response.status_code == 204
    assert response.content == b""
    assert fake_db.commit_count == 0
    assert fake_db.deleted == []

    app.dependency_overrides.clear()


def test_unlike_movie_deletes_like_and_commits():
    existing_like = object()
    fake_db = FakeDB(query_results=[existing_like])
    app = create_test_app(fake_db)
    client = TestClient(app)

    response = client.delete("/likes/55")

    assert response.status_code == 204
    assert response.content == b""
    assert fake_db.commit_count == 1
    assert fake_db.deleted == [existing_like]

    app.dependency_overrides.clear()


def test_likes_routes_require_auth_for_get():
    fake_db = FakeDB(query_results=[None])
    app = create_test_app(fake_db, override_auth=False)
    client = TestClient(app)

    response = client.get("/likes/10")

    assert response.status_code in (401, 403)

    app.dependency_overrides.clear()


def test_likes_routes_require_auth_for_post():
    fake_db = FakeDB(query_results=[object(), None])
    app = create_test_app(fake_db, override_auth=False)
    client = TestClient(app)

    response = client.post("/likes/10")

    assert response.status_code in (401, 403)

    app.dependency_overrides.clear()


def test_likes_routes_require_auth_for_delete():
    fake_db = FakeDB(query_results=[object()])
    app = create_test_app(fake_db, override_auth=False)
    client = TestClient(app)

    response = client.delete("/likes/10")

    assert response.status_code in (401, 403)

    app.dependency_overrides.clear()


def test_likes_route_rejects_non_integer_movie_id():
    fake_db = FakeDB(query_results=[])
    app = create_test_app(fake_db)
    client = TestClient(app)

    response = client.get("/likes/not-an-int")

    assert response.status_code == 422

    app.dependency_overrides.clear()