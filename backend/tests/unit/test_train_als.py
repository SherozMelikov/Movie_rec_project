## pytest tests/unit/test_train_als.py


import json
import numpy as np
import pytest

from app.ml.scripts import train_als as als_module


def test_event_weight_returns_expected_values():
    assert als_module.event_weight("view", None) == 0.25
    assert als_module.event_weight("like", None) == 4.0
    assert als_module.event_weight("rate", 1) == 0.2
    assert als_module.event_weight("rate", 2) == 0.5
    assert als_module.event_weight("rate", 3) == 1.0
    assert als_module.event_weight("rate", 4) == 2.0
    assert als_module.event_weight("rate", 5) == 3.0


def test_event_weight_returns_zero_for_unknown_event():
    assert als_module.event_weight("bookmark", None) == 0.0
    assert als_module.event_weight("share", None) == 0.0


def test_train_als_creates_expected_artifact_files(tmp_path, monkeypatch):
    monkeypatch.setattr(als_module, "ART_DIR", str(tmp_path))

    fake_events = [
        (1, 101, "view", None),
        (1, 101, "like", None),
        (1, 102, "rate", 5),
        (2, 101, "view", None),
        (2, 103, "like", None),
    ]
    fake_onboarding = [
        (1, 103),
        (2, 102),
    ]

    monkeypatch.setattr(
        als_module,
        "load_events_and_onboarding",
        lambda: (fake_events, fake_onboarding),
    )

    result = als_module.train_als()

    assert result["users"] == 2
    assert result["items"] == 3
    assert result["pairs"] > 0

    assert (tmp_path / "user_factors.npy").exists()
    assert (tmp_path / "item_factors.npy").exists()
    assert (tmp_path / "user_id_to_idx.json").exists()
    assert (tmp_path / "movie_id_to_idx.json").exists()
    assert (tmp_path / "meta.json").exists()


def test_train_als_saves_factor_shapes_matching_users_and_items(tmp_path, monkeypatch):
    monkeypatch.setattr(als_module, "ART_DIR", str(tmp_path))

    fake_events = [
        (1, 101, "like", None),
        (1, 102, "rate", 4),
        (2, 101, "view", None),
        (2, 103, "like", None),
        (3, 104, "rate", 5),
    ]
    fake_onboarding = [
        (3, 101),
    ]

    monkeypatch.setattr(
        als_module,
        "load_events_and_onboarding",
        lambda: (fake_events, fake_onboarding),
    )

    result = als_module.train_als()

    user_factors = np.load(tmp_path / "user_factors.npy")
    item_factors = np.load(tmp_path / "item_factors.npy")

    assert user_factors.shape[0] == result["users"]
    assert item_factors.shape[0] == result["items"]
    assert user_factors.shape[1] == als_module.FACTORS
    assert item_factors.shape[1] == als_module.FACTORS

def test_train_als_saves_expected_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(als_module, "ART_DIR", str(tmp_path))

    fake_events = [
        (1, 101, "view", None),
        (1, 101, "like", None),
        (2, 102, "rate", 5),
    ]
    fake_onboarding = [
        (2, 101),
    ]

    monkeypatch.setattr(
        als_module,
        "load_events_and_onboarding",
        lambda: (fake_events, fake_onboarding),
    )

    result = als_module.train_als()

    meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))

    assert meta["model"] == "implicit_als"
    assert meta["factors"] == als_module.FACTORS
    assert meta["iterations"] == als_module.ITERATIONS
    assert meta["regularization"] == als_module.REGULARIZATION
    assert meta["users"] == result["users"]
    assert meta["items"] == result["items"]
    assert meta["pairs"] == result["pairs"]

    assert meta["weights"]["view"] == als_module.W_VIEW
    assert meta["weights"]["like"] == als_module.W_LIKE
    assert meta["weights"]["onboarding"] == als_module.W_ONBOARD

    expected_rate_map = {str(k): v for k, v in als_module.RATE_MAP.items()}
    assert meta["weights"]["rate_map"] == expected_rate_map
    
def test_train_als_raises_when_no_events_or_onboarding(tmp_path, monkeypatch):
    monkeypatch.setattr(als_module, "ART_DIR", str(tmp_path))
    monkeypatch.setattr(
        als_module,
        "load_events_and_onboarding",
        lambda: ([], []),
    )

    with pytest.raises(RuntimeError, match="No events or onboarding interactions found"):
        als_module.train_als()


def test_train_als_view_aggregation_uses_max_not_sum(tmp_path, monkeypatch):
    monkeypatch.setattr(als_module, "ART_DIR", str(tmp_path))

    # repeated views for same user-item should not stack beyond max(view weight)
    fake_events = [
        (1, 101, "view", None),
        (1, 101, "view", None),
        (1, 101, "view", None),
        (2, 102, "like", None),
    ]
    fake_onboarding = []

    monkeypatch.setattr(
        als_module,
        "load_events_and_onboarding",
        lambda: (fake_events, fake_onboarding),
    )

    result = als_module.train_als()
    meta = result["meta"]

    assert result["users"] == 2
    assert result["items"] == 2
    assert result["pairs"] == 2
    assert meta["model"] == "implicit_als"