from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

import app.services.recommend_service as svc


def make_item(movie_id: int, title: str | None = None) -> svc.RecommendationItem:
    return svc.RecommendationItem(
        movie_id=movie_id,
        title=title or f"Movie {movie_id}",
        genres="Action",
        poster_url=None,
        release_date=None,
        reason="test",
        score=None,
    )


@pytest.fixture
def service():
    config = svc.RecommendConfig(
        min_candidate_k=3,
        max_candidate_k=10,
        candidate_multiplier=2,
        als_candidate_k=5,
        exclude_max_rows=50,
        trending_days=7,
        debug_pipeline=False,
        debug_rerank=False,
    )
    return svc.RecommendService(config=config)


def test_prepare_context_uses_forced_inputs_and_merges_seed_ids_into_excludes(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_get_seed_movies_blended",
        lambda *args, **kwargs: pytest.fail("_get_seed_movies_blended should not be called"),
    )
    monkeypatch.setattr(
        service,
        "_get_excluded_movie_ids",
        lambda *args, **kwargs: pytest.fail("_get_excluded_movie_ids should not be called"),
    )
    monkeypatch.setattr(svc.als_recommender, "can_score_user", lambda user_id: True)
    monkeypatch.setattr(service, "_interaction_count", lambda db, user_id, as_of_ts=None: 7)

    seed_ids, exclude_ids, has_als, interaction_count = service._prepare_context(
        db=object(),
        user_id=123,
        force_seed_ids=[10, 20],
        force_exclude_ids={30, 40},
    )

    assert seed_ids == [10, 20]
    assert exclude_ids == {10, 20, 30, 40}
    assert has_als is True
    assert interaction_count == 7


@pytest.mark.parametrize(
    ("has_als", "interaction_count", "seed_movie_ids", "expected_strategy"),
    [
        (True, 20, [1], "als_only"),
        (True, 5, [1], "hybrid_light"),
        (True, 5, [], "als_only"),
        (False, 5, [1], "cbf_only"),
        (False, 0, [], "trending_fallback"),
    ],
)
def test_choose_strategy_returns_expected_result(
    service, has_als, interaction_count, seed_movie_ids, expected_strategy
):
    strategy, reason = service._choose_strategy(
        has_als=has_als,
        interaction_count=interaction_count,
        seed_movie_ids=seed_movie_ids,
    )

    assert strategy == expected_strategy
    assert isinstance(reason, str)
    assert reason


def test_get_for_user_als_only_returns_items_from_als(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_prepare_context",
        lambda **kwargs: ([10], {10, 11}, True, 25),
    )

    calls = {}

    def fake_top_n(user_id, exclude_ids, n):
        calls["top_n"] = {
            "user_id": user_id,
            "exclude_ids": exclude_ids,
            "n": n,
        }
        return [101, 102, 103]

    def fake_score_candidates(user_id, movie_ids):
        calls["score_candidates"] = {
            "user_id": user_id,
            "movie_ids": movie_ids,
        }
        return {101: 0.91, 102: 0.82}

    def fake_items_from_ids(db, movie_ids, reason, score_map):
        calls["items_from_ids"] = {
            "movie_ids": movie_ids,
            "reason": reason,
            "score_map": score_map,
        }
        return [make_item(101), make_item(102)]

    monkeypatch.setattr(svc.als_recommender, "top_n", fake_top_n)
    monkeypatch.setattr(svc.als_recommender, "score_candidates", fake_score_candidates)
    monkeypatch.setattr(service, "_items_from_ids", fake_items_from_ids)

    result = service.get_for_user(db=object(), user_id=1, limit=2)

    assert [item.movie_id for item in result] == [101, 102]
    assert calls["top_n"] == {
        "user_id": 1,
        "exclude_ids": {10, 11},
        "n": 5,
    }
    assert calls["score_candidates"] == {
        "user_id": 1,
        "movie_ids": [101, 102],
    }
    assert calls["items_from_ids"]["reason"] == "Based on collaborative patterns"
    assert calls["items_from_ids"]["score_map"] == {101: 0.91, 102: 0.82}


def test_get_for_user_hybrid_light_returns_hybrid_items(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_prepare_context",
        lambda **kwargs: ([10, 20], {10, 20, 30}, True, 8),
    )

    debug_info = SimpleNamespace(strategy="hybrid", reason="hybrid ok", warnings=[])

    monkeypatch.setattr(
        svc.hybrid_recommender,
        "recommend_ids",
        lambda **kwargs: ([201, 202], {201: 0.7, 202: 0.6}, "Hybrid picks", debug_info),
    )
    monkeypatch.setattr(
        service,
        "_items_from_ids",
        lambda db, movie_ids, reason, score_map: [make_item(mid) for mid in movie_ids],
    )

    result = service.get_for_user(db=object(), user_id=1, limit=2)

    assert [item.movie_id for item in result] == [201, 202]


def test_get_for_user_hybrid_light_falls_back_to_als_when_hybrid_is_empty(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_prepare_context",
        lambda **kwargs: ([10], {10, 11}, True, 6),
    )

    debug_info = SimpleNamespace(strategy="hybrid", reason="empty", warnings=["no candidates"])

    monkeypatch.setattr(
        svc.hybrid_recommender,
        "recommend_ids",
        lambda **kwargs: ([], {}, "Hybrid picks", debug_info),
    )
    monkeypatch.setattr(
        svc.als_recommender,
        "top_n",
        lambda user_id, exclude_ids, n: [301, 302],
    )
    monkeypatch.setattr(
        svc.als_recommender,
        "score_candidates",
        lambda user_id, movie_ids: {301: 0.55, 302: 0.44},
    )
    monkeypatch.setattr(
        service,
        "_items_from_ids",
        lambda db, movie_ids, reason, score_map: [make_item(mid) for mid in movie_ids],
    )

    result = service.get_for_user(db=object(), user_id=1, limit=2)

    assert [item.movie_id for item in result] == [301, 302]


def test_get_for_user_hybrid_light_falls_back_to_cbf_when_no_als(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_prepare_context",
        lambda **kwargs: ([10], {10, 11}, False, 3),
    )

    debug_info = SimpleNamespace(strategy="hybrid", reason="empty", warnings=["no candidates"])

    monkeypatch.setattr(
        svc.hybrid_recommender,
        "recommend_ids",
        lambda **kwargs: ([], {}, "Hybrid picks", debug_info),
    )
    monkeypatch.setattr(
        svc.cbf_recommender,
        "top_n_from_seeds",
        lambda seed_movie_ids, exclude_ids, n, search_k: ([401, 402], {401: 0.8, 402: 0.7}),
    )
    monkeypatch.setattr(
        service,
        "_items_from_ids",
        lambda db, movie_ids, reason, score_map: [make_item(mid) for mid in movie_ids],
    )

    result = service.get_for_user(db=object(), user_id=1, limit=2)

    assert [item.movie_id for item in result] == [401, 402]


def test_get_for_user_cbf_only_returns_cbf_items(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_prepare_context",
        lambda **kwargs: ([10, 20], {10, 20}, False, 2),
    )
    monkeypatch.setattr(
        svc.cbf_recommender,
        "top_n_from_seeds",
        lambda seed_movie_ids, exclude_ids, n, search_k: ([501, 502], {501: 0.9, 502: 0.8}),
    )
    monkeypatch.setattr(
        service,
        "_items_from_ids",
        lambda db, movie_ids, reason, score_map: [make_item(mid) for mid in movie_ids],
    )

    result = service.get_for_user(db=object(), user_id=1, limit=2)

    assert [item.movie_id for item in result] == [501, 502]


def test_get_for_user_returns_trending_fallback_when_no_signal(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_prepare_context",
        lambda **kwargs: ([], set(), False, 0),
    )
    monkeypatch.setattr(
        service,
        "_get_trending_movies",
        lambda db, limit, days: [SimpleNamespace(movie_id=601), SimpleNamespace(movie_id=602)],
    )
    monkeypatch.setattr(
        service,
        "_items_from_movies",
        lambda db, movies, reason, score_map: [make_item(m.movie_id) for m in movies],
    )

    result = service.get_for_user(db=object(), user_id=1, limit=2)

    assert [item.movie_id for item in result] == [601, 602]


def test_get_for_user_for_eval_hybrid_falls_back_to_als(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_prepare_context",
        lambda **kwargs: ([10], {10}, True, 4),
    )
    monkeypatch.setattr(
        svc.hybrid_recommender,
        "recommend_ids",
        lambda **kwargs: ([], {}, "empty", None),
    )
    monkeypatch.setattr(
        svc.als_recommender,
        "top_n",
        lambda user_id, exclude_ids, n: [701, 702, 703],
    )

    result = service.get_for_user_for_eval(db=object(), user_id=1, limit=2)

    assert result == [701, 702]


def test_get_hybrid_ids_for_eval_uses_max_candidate_k(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_prepare_context",
        lambda **kwargs: ([10], {10, 11}, False, 4),
    )

    calls = {}

    def fake_recommend_ids(**kwargs):
        calls["kwargs"] = kwargs
        return [801, 802], {801: 0.9}, "hybrid", None

    monkeypatch.setattr(svc.hybrid_recommender, "recommend_ids", fake_recommend_ids)

    result = service.get_hybrid_ids_for_eval(db=object(), user_id=1, limit=2)

    assert result == [801, 802]
    assert calls["kwargs"]["als_candidate_k"] == 10
    assert calls["kwargs"]["cbf_candidate_k"] == 10
    assert calls["kwargs"]["search_k"] == 10


def test_get_sections_for_user_builds_deduped_sections(service, monkeypatch):
    monkeypatch.setattr(service, "_get_seed_movies_blended", lambda db, user_id, as_of_ts=None: [10])
    monkeypatch.setattr(
        service,
        "_get_excluded_movie_ids",
        lambda db, user_id, as_of_ts=None, max_rows=50: [99],
    )

    monkeypatch.setattr(
        service,
        "get_for_user",
        lambda db, user_id, limit, as_of_ts=None: [make_item(1), make_item(2)],
    )

    trending_calls = {"count": 0}

    def fake_get_trending_movies(db, limit, days=7):
        trending_calls["count"] += 1
        if trending_calls["count"] == 1:
            return [SimpleNamespace(movie_id=2), SimpleNamespace(movie_id=3)]
        if trending_calls["count"] == 2:
            return [SimpleNamespace(movie_id=4)]
        return [SimpleNamespace(movie_id=5)]

    monkeypatch.setattr(service, "_get_trending_movies", fake_get_trending_movies)
    monkeypatch.setattr(service, "_get_hidden_gems", lambda db, limit, days=30: [SimpleNamespace(movie_id=7), SimpleNamespace(movie_id=99)])

    def fake_items_from_movies(db, movies, reason, score_map):
        return [make_item(m.movie_id) for m in movies]

    def fake_items_from_ids(db, movie_ids, reason, score_map):
        return [make_item(mid) for mid in movie_ids]

    monkeypatch.setattr(service, "_items_from_movies", fake_items_from_movies)
    monkeypatch.setattr(service, "_items_from_ids", fake_items_from_ids)

    monkeypatch.setattr(
        svc.cbf_recommender,
        "more_like_movie_ids",
        lambda seed_movie_id, exclude_ids, limit: [2, 6, 7],
    )

    sections = service.get_sections_for_user(db=object(), user_id=1, limit_per_section=2)

    assert [section.title for section in sections] == [
        "Top Picks for You",
        "Trending Now",
        "Because You Liked",
    ]
    assert [[item.movie_id for item in section.items] for section in sections] == [
        [1, 2],
        [3, 4],
        [6, 7],
    ]


def test_items_from_ids_preserves_input_order_and_uses_metadata(monkeypatch, service):
    monkeypatch.setattr(svc, "build_poster_url", lambda path: f"https://img{path}")

    movies = [
        SimpleNamespace(movie_id=2, title="Movie 2", genres="Drama"),
        SimpleNamespace(movie_id=1, title="Movie 1", genres="Action"),
    ]
    metas = [
        SimpleNamespace(movie_id=1, poster_path="/a.jpg", release_date=date(2001, 1, 1)),
    ]

    class FakeQuery:
        def __init__(self, results):
            self._results = results

        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return self._results

    class FakeDB:
        def query(self, model):
            if model is svc.Movie:
                return FakeQuery(movies)
            if model is svc.MovieMetadata:
                return FakeQuery(metas)
            raise AssertionError(f"Unexpected model: {model}")

    result = service._items_from_ids(
        db=FakeDB(),
        movie_ids=[1, 2],
        reason="Because test",
        score_map={1: 0.9},
    )

    assert [item.movie_id for item in result] == [1, 2]
    assert result[0].poster_url == "https://img/a.jpg"
    assert result[0].release_date == date(2001, 1, 1)
    assert result[0].score == 0.9
    assert result[1].poster_url is None
    assert result[1].score is None


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeQuery:
    def __init__(self, results):
        self._results = results
        self._limit = None

    def filter(self, *args, **kwargs):
        return self

    def limit(self, limit):
        self._limit = limit
        return self

    def all(self):
        if self._limit is None:
            return self._results
        return self._results[: self._limit]


class _FakeDB:
    def __init__(self, execute_fn=None, movie_results=None, metadata_results=None):
        self._execute_fn = execute_fn or (lambda sql, params: [])
        self._movie_results = movie_results or []
        self._metadata_results = metadata_results or []

    def execute(self, sql, params):
        return _FakeResult(self._execute_fn(str(sql), params))

    def query(self, model):
        if model is svc.Movie:
            return _FakeQuery(self._movie_results)
        if model is svc.MovieMetadata:
            return _FakeQuery(self._metadata_results)
        raise AssertionError(f"Unexpected model: {model}")


def test_get_for_user_als_only_falls_back_to_trending_when_als_empty(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_prepare_context",
        lambda **kwargs: ([], {10, 11}, True, 25),
    )
    monkeypatch.setattr(svc.als_recommender, "top_n", lambda user_id, exclude_ids, n: [])
    monkeypatch.setattr(
        service,
        "_get_trending_movies",
        lambda db, limit, days: [SimpleNamespace(movie_id=901), SimpleNamespace(movie_id=902)],
    )
    monkeypatch.setattr(
        service,
        "_items_from_movies",
        lambda db, movies, reason, score_map: [make_item(m.movie_id) for m in movies],
    )

    result = service.get_for_user(db=object(), user_id=1, limit=2)

    assert [item.movie_id for item in result] == [901, 902]


def test_get_for_user_cbf_only_falls_back_to_trending_when_cbf_empty(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_prepare_context",
        lambda **kwargs: ([10], {10, 11}, False, 2),
    )
    monkeypatch.setattr(
        svc.cbf_recommender,
        "top_n_from_seeds",
        lambda seed_movie_ids, exclude_ids, n, search_k: ([], {}),
    )
    monkeypatch.setattr(
        service,
        "_get_trending_movies",
        lambda db, limit, days: [SimpleNamespace(movie_id=903), SimpleNamespace(movie_id=904)],
    )
    monkeypatch.setattr(
        service,
        "_items_from_movies",
        lambda db, movies, reason, score_map: [make_item(m.movie_id) for m in movies],
    )

    result = service.get_for_user(db=object(), user_id=1, limit=2)

    assert [item.movie_id for item in result] == [903, 904]


def test_get_for_user_for_eval_als_only_returns_top_n(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_prepare_context",
        lambda **kwargs: ([], {10}, True, 22),
    )
    monkeypatch.setattr(
        svc.als_recommender,
        "top_n",
        lambda user_id, exclude_ids, n: [1001, 1002, 1003],
    )

    result = service.get_for_user_for_eval(db=object(), user_id=1, limit=2)

    assert result == [1001, 1002]


def test_get_for_user_for_eval_hybrid_returns_ids_directly(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_prepare_context",
        lambda **kwargs: ([10], {10}, True, 5),
    )
    monkeypatch.setattr(
        svc.hybrid_recommender,
        "recommend_ids",
        lambda **kwargs: ([1101, 1102], {1101: 0.9}, "hybrid", None),
    )

    result = service.get_for_user_for_eval(db=object(), user_id=1, limit=2)

    assert result == [1101, 1102]


def test_get_for_user_for_eval_hybrid_falls_back_to_cbf_when_no_als(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_prepare_context",
        lambda **kwargs: ([10], {10}, False, 4),
    )
    monkeypatch.setattr(
        svc.hybrid_recommender,
        "recommend_ids",
        lambda **kwargs: ([], {}, "empty", None),
    )
    monkeypatch.setattr(
        svc.cbf_recommender,
        "top_n_from_seeds",
        lambda seed_movie_ids, exclude_ids, n, search_k: ([1201, 1202], {1201: 0.7}),
    )

    result = service.get_for_user_for_eval(db=object(), user_id=1, limit=2)

    assert result == [1201, 1202]


def test_get_for_user_for_eval_cbf_only_returns_ids(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_prepare_context",
        lambda **kwargs: ([10], {10}, False, 2),
    )
    monkeypatch.setattr(
        svc.cbf_recommender,
        "top_n_from_seeds",
        lambda seed_movie_ids, exclude_ids, n, search_k: ([1301, 1302], {1301: 0.8}),
    )

    result = service.get_for_user_for_eval(db=object(), user_id=1, limit=2)

    assert result == [1301, 1302]


def test_get_for_user_for_eval_trending_fallback_returns_empty(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_prepare_context",
        lambda **kwargs: ([], set(), False, 0),
    )

    result = service.get_for_user_for_eval(db=object(), user_id=1, limit=2)

    assert result == []


def test_items_from_ids_returns_empty_for_no_ids(service):
    result = service._items_from_ids(
        db=object(),
        movie_ids=[],
        reason="none",
        score_map=None,
    )
    assert result == []


def test_items_from_movies_delegates_to_items_from_ids(service, monkeypatch):
    calls = {}

    def fake_items_from_ids(db, movie_ids, reason, score_map):
        calls["movie_ids"] = movie_ids
        calls["reason"] = reason
        calls["score_map"] = score_map
        return [make_item(mid) for mid in movie_ids]

    monkeypatch.setattr(service, "_items_from_ids", fake_items_from_ids)

    movies = [SimpleNamespace(movie_id=1401), SimpleNamespace(movie_id=1402)]

    result = service._items_from_movies(
        db=object(),
        movies=movies,
        reason="Trending now",
        score_map={1401: 0.5},
    )

    assert [item.movie_id for item in result] == [1401, 1402]
    assert calls == {
        "movie_ids": [1401, 1402],
        "reason": "Trending now",
        "score_map": {1401: 0.5},
    }


def test_dedup_items_skips_used_and_updates_used_ids(service):
    used = {1}
    items = [make_item(1), make_item(2), make_item(2), make_item(3)]

    result = service._dedup_items(items, used, limit=2)

    assert [item.movie_id for item in result] == [2, 3]
    assert used == {1, 2, 3}


def test_get_seed_movies_blended_merges_dedupes_and_limits(service):
    def execute_fn(sql, params):
        if "user_onboarding_movies" in sql:
            return [(6,), (7,), (8,)]
        return [(5,), (6,)]

    db = _FakeDB(execute_fn=execute_fn)

    result = service._get_seed_movies_blended(db=db, user_id=1)

    assert result == [5, 6, 7, 8]


def test_get_excluded_movie_ids_returns_int_ids(service):
    db = _FakeDB(execute_fn=lambda sql, params: [(10,), (20,), (30,)])

    result = service._get_excluded_movie_ids(db=db, user_id=1, max_rows=50)

    assert result == [10, 20, 30]


def test_get_trending_movies_falls_back_to_plain_movie_query_when_no_rows(service):
    fallback_movies = [
        SimpleNamespace(movie_id=1501, title="A", genres="Action"),
        SimpleNamespace(movie_id=1502, title="B", genres="Drama"),
    ]
    db = _FakeDB(
        execute_fn=lambda sql, params: [],
        movie_results=fallback_movies,
    )

    result = service._get_trending_movies(db=db, limit=2, days=7)

    assert result == fallback_movies


def test_get_trending_movies_preserves_ranked_order(service):
    movies = [
        SimpleNamespace(movie_id=1502, title="B", genres="Drama"),
        SimpleNamespace(movie_id=1501, title="A", genres="Action"),
    ]
    db = _FakeDB(
        execute_fn=lambda sql, params: [(1501,), (1502,), (9999,)],
        movie_results=movies,
    )

    result = service._get_trending_movies(db=db, limit=3, days=7)

    assert [m.movie_id for m in result] == [1501, 1502]


def test_get_hidden_gems_returns_empty_when_no_rows(service):
    db = _FakeDB(execute_fn=lambda sql, params: [])

    result = service._get_hidden_gems(db=db, limit=3, days=30)

    assert result == []


def test_get_hidden_gems_preserves_ranked_order(service):
    movies = [
        SimpleNamespace(movie_id=1602, title="B", genres="Drama"),
        SimpleNamespace(movie_id=1601, title="A", genres="Action"),
    ]
    db = _FakeDB(
        execute_fn=lambda sql, params: [(1601,), (1602,), (9999,)],
        movie_results=movies,
    )

    result = service._get_hidden_gems(db=db, limit=3, days=30)

    assert [m.movie_id for m in result] == [1601, 1602]


def test_interaction_count_returns_integer(service):
    db = _FakeDB(execute_fn=lambda sql, params: [(7,)])

    result = service._interaction_count(db=db, user_id=1)

    assert result == 7    