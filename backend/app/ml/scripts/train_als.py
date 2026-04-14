import os
import json
from collections import defaultdict
from typing import Any

import numpy as np
from sqlalchemy import text
from scipy.sparse import coo_matrix
from implicit.als import AlternatingLeastSquares

from app.db.database import SessionLocal

ART_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts", "als")
os.makedirs(ART_DIR, exist_ok=True)

# -----------------------
# Training hyperparameters
# -----------------------
FACTORS = 64
ITERATIONS = 20
REGULARIZATION = 0.01

# -----------------------
# Event weights
# -----------------------
W_VIEW = 0.25
W_LIKE = 4.0
W_ONBOARD = 3.0
RATE_MAP = {1: 0.2, 2: 0.5, 3: 1.0, 4: 2.0, 5: 3.0}


def event_weight(event_type: str, rating_value: Any) -> float:
    if event_type == "view":
        return W_VIEW
    if event_type == "like":
        return W_LIKE
    if event_type == "rate":
        return float(RATE_MAP.get(int(rating_value or 3), 1.0))
    return 0.0


def load_events_and_onboarding():
    db = SessionLocal()
    try:
        events = db.execute(text("""
            SELECT user_id, movie_id, event_type, rating_value
            FROM interactions_all
            WHERE user_id IS NOT NULL
              AND movie_id IS NOT NULL
        """)).fetchall()

        onboarding = db.execute(text("""
            SELECT user_id, movie_id
            FROM user_onboarding_movies
            WHERE user_id IS NOT NULL
              AND movie_id IS NOT NULL
        """)).fetchall()

        return events, onboarding
    finally:
        db.close()


def train_als() -> dict:
    print("✅ ALS artifact dir:", os.path.abspath(ART_DIR))

    events, onboarding = load_events_and_onboarding()
    if not events and not onboarding:
        raise RuntimeError("No events or onboarding interactions found.")

    # Aggregate interactions per (user_id, movie_id)
    # - views: max to avoid view spam
    # - likes/rates/onboarding: sum
    agg = defaultdict(float)
    users = set()
    items = set()

    for user_id, movie_id, event_type, rating_value in events:
        w = event_weight(event_type, rating_value)
        if w <= 0:
            continue

        u = int(user_id)
        i = int(movie_id)

        if event_type == "view":
            agg[(u, i)] = max(agg[(u, i)], w)
        else:
            agg[(u, i)] += w

        users.add(u)
        items.add(i)

    for user_id, movie_id in onboarding:
        u = int(user_id)
        i = int(movie_id)
        agg[(u, i)] += W_ONBOARD
        users.add(u)
        items.add(i)

    users = sorted(users)
    items = sorted(items)

    print(f"Users: {len(users)} | Items: {len(items)} | Pairs: {len(agg)}")
    print(f"Event rows: {len(events)} | Onboarding rows: {len(onboarding)}")

    if not users or not items or not agg:
        raise RuntimeError("ALS training aborted: no usable users/items/interactions after aggregation.")

    user_id_to_idx = {uid: idx for idx, uid in enumerate(users)}
    movie_id_to_idx = {mid: idx for idx, mid in enumerate(items)}

    row = np.empty(len(agg), dtype=np.int32)
    col = np.empty(len(agg), dtype=np.int32)
    data = np.empty(len(agg), dtype=np.float32)

    for k, ((uid, mid), w) in enumerate(agg.items()):
        row[k] = user_id_to_idx[uid]
        col[k] = movie_id_to_idx[mid]
        data[k] = float(w)

    # user-item matrix
    mat = coo_matrix((data, (row, col)), shape=(len(users), len(items))).tocsr()

    model = AlternatingLeastSquares(
        factors=FACTORS,
        regularization=REGULARIZATION,
        iterations=ITERATIONS,
        random_state=42,
    )

    # implicit ALS expects item-user matrix
    item_user = mat.T.tocsr()
    model.fit(item_user)
    # Because we trained on mat.T:
    # model.item_factors correspond to original users
    # model.user_factors correspond to original items
    np.save(os.path.join(ART_DIR, "user_factors.npy"), model.item_factors.astype(np.float32))
    np.save(os.path.join(ART_DIR, "item_factors.npy"), model.user_factors.astype(np.float32))

    with open(os.path.join(ART_DIR, "user_id_to_idx.json"), "w", encoding="utf-8") as f:
        json.dump(user_id_to_idx, f)

    with open(os.path.join(ART_DIR, "movie_id_to_idx.json"), "w", encoding="utf-8") as f:
        json.dump(movie_id_to_idx, f)

    meta = {
        "model": "implicit_als",
        "factors": FACTORS,
        "iterations": ITERATIONS,
        "regularization": REGULARIZATION,
        "users": len(users),
        "items": len(items),
        "pairs": len(agg),
        "weights": {
            "view": W_VIEW,
            "like": W_LIKE,
            "onboarding": W_ONBOARD,
            "rate_map": RATE_MAP,
        },
    }

    with open(os.path.join(ART_DIR, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print("✅ Saved ALS artifacts to:", ART_DIR)

    return {
        "artifact_dir": os.path.abspath(ART_DIR),
        "users": len(users),
        "items": len(items),
        "pairs": len(agg),
        "meta": meta,
    }


if __name__ == "__main__":
    train_als()