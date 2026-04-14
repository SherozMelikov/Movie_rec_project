from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.recommendations as rec_api
from app.schemas.schemas import RecommendationItem, RecommendationSection


def make_item(movie_id: int, title: str | None = None) -> RecommendationItem:
    return RecommendationItem(
        movie_id=movie_id,
        title=title or f"Movie {movie_id}",
        genres="Action",
        poster_url=None,
        release_date=None,
        reason="test",
        score=0.9,
    )


def create_test_app(*, override_auth: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(rec_api.router, prefix="/recommendations")

    def fake_db():
        yield object()

    app.dependency_overrides[rec_api.get_db] = fake_db

    if override_auth:
        app.dependency_overrides[rec_api.get_current_user] = lambda: SimpleNamespace(user_id=123)

    return app


@pytest.fixture
def app():
    app = create_test_app(override_auth=True)
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(app):
    return TestClient(app)


def test_get_recommendations_returns_items_and_calls_service(client, monkeypatch):
    calls = {}

    def fake_get_for_user(db, user_id, limit):
        calls["db"] = db
        calls["user_id"] = user_id
        calls["limit"] = limit
        return [make_item(1), make_item(2)]

    monkeypatch.setattr(rec_api.recommend_service, "get_for_user", fake_get_for_user)

    response = client.get("/recommendations?limit=12")

    assert response.status_code == 200
    assert response.json() == [
        {
            "movie_id": 1,
            "title": "Movie 1",
            "genres": "Action",
            "poster_url": None,
            "release_date": None,
            "reason": "test",
            "score": 0.9,
        },
        {
            "movie_id": 2,
            "title": "Movie 2",
            "genres": "Action",
            "poster_url": None,
            "release_date": None,
            "reason": "test",
            "score": 0.9,
        },
    ]
    assert calls["user_id"] == 123
    assert calls["limit"] == 12


def test_get_recommendations_uses_default_limit(client, monkeypatch):
    calls = {}

    def fake_get_for_user(db, user_id, limit):
        calls["limit"] = limit
        return []

    monkeypatch.setattr(rec_api.recommend_service, "get_for_user", fake_get_for_user)

    response = client.get("/recommendations")

    assert response.status_code == 200
    assert response.json() == []
    assert calls["limit"] == 50


def test_get_recommendations_rejects_limit_too_low(client):
    response = client.get("/recommendations?limit=5")

    assert response.status_code == 422


def test_get_recommendations_rejects_limit_too_high(client):
    response = client.get("/recommendations?limit=101")

    assert response.status_code == 422


def test_get_recommendations_sections_returns_sections_and_calls_service(client, monkeypatch):
    calls = {}

    def fake_get_sections_for_user(db, user_id, limit_per_section):
        calls["db"] = db
        calls["user_id"] = user_id
        calls["limit_per_section"] = limit_per_section
        return [
            RecommendationSection(
                title="Top Picks for You",
                subtitle="Based on your activity",
                items=[make_item(10)],
            ),
            RecommendationSection(
                title="Trending Now",
                subtitle="Popular right now",
                items=[make_item(20), make_item(21)],
            ),
        ]

    monkeypatch.setattr(rec_api.recommend_service, "get_sections_for_user", fake_get_sections_for_user)

    response = client.get("/recommendations/sections?limit_per_section=6")

    assert response.status_code == 200
    assert response.json() == [
        {
            "title": "Top Picks for You",
            "subtitle": "Based on your activity",
            "items": [
                {
                    "movie_id": 10,
                    "title": "Movie 10",
                    "genres": "Action",
                    "poster_url": None,
                    "release_date": None,
                    "reason": "test",
                    "score": 0.9,
                }
            ],
        },
        {
            "title": "Trending Now",
            "subtitle": "Popular right now",
            "items": [
                {
                    "movie_id": 20,
                    "title": "Movie 20",
                    "genres": "Action",
                    "poster_url": None,
                    "release_date": None,
                    "reason": "test",
                    "score": 0.9,
                },
                {
                    "movie_id": 21,
                    "title": "Movie 21",
                    "genres": "Action",
                    "poster_url": None,
                    "release_date": None,
                    "reason": "test",
                    "score": 0.9,
                },
            ],
        },
    ]
    assert calls["user_id"] == 123
    assert calls["limit_per_section"] == 6


def test_get_recommendations_sections_uses_default_limit(client, monkeypatch):
    calls = {}

    def fake_get_sections_for_user(db, user_id, limit_per_section):
        calls["limit_per_section"] = limit_per_section
        return []

    monkeypatch.setattr(rec_api.recommend_service, "get_sections_for_user", fake_get_sections_for_user)

    response = client.get("/recommendations/sections")

    assert response.status_code == 200
    assert response.json() == []
    assert calls["limit_per_section"] == 12


def test_get_recommendations_sections_rejects_limit_too_low(client):
    response = client.get("/recommendations/sections?limit_per_section=5")

    assert response.status_code == 422


def test_get_recommendations_sections_rejects_limit_too_high(client):
    response = client.get("/recommendations/sections?limit_per_section=31")

    assert response.status_code == 422


def test_get_recommendations_requires_auth(monkeypatch):
    app = create_test_app(override_auth=False)

    monkeypatch.setattr(
        rec_api.recommend_service,
        "get_for_user",
        lambda db, user_id, limit: pytest.fail("service should not be called without auth"),
    )

    client = TestClient(app)
    response = client.get("/recommendations?limit=12")

    assert response.status_code in (401, 403)

    app.dependency_overrides.clear()


def test_get_recommendations_sections_requires_auth(monkeypatch):
    app = create_test_app(override_auth=False)

    monkeypatch.setattr(
        rec_api.recommend_service,
        "get_sections_for_user",
        lambda db, user_id, limit_per_section: pytest.fail("service should not be called without auth"),
    )

    client = TestClient(app)
    response = client.get("/recommendations/sections?limit_per_section=6")

    assert response.status_code in (401, 403)

    app.dependency_overrides.clear()