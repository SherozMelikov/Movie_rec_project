import os
import json
from collections import defaultdict

import numpy as np
from sqlalchemy import text
from scipy.sparse import coo_matrix, csr_matrix

from implicit.als import AlternatingLeastSquares

from app.db.database import SessionLocal

ART_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts", "als")

print("✅ ART_DIR (ABS):", os.path.abspath(ART_DIR))



os.makedirs(ART_DIR, exist_ok=True)

# ---- knobs ----
FACTORS = 64
ITERATIONS = 20
REGULARIZATION = 0.01

# event weights (tune later)
W_VIEW = 0.25
W_LIKE = 4.0
W_ONBOARD = 3.0
RATE_MAP = {1: 0.2, 2: 0.5, 3: 1.0, 4: 2.0, 5: 3.0}


def event_weight(event_type: str, rating_value):
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
        """)).fetchall()


        onboarding = db.execute(text("""
            SELECT user_id, movie_id
            FROM user_onboarding_movies
        """)).fetchall()

        return events, onboarding
    finally:
        db.close()


def main():
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

    print(f"Users: {len(users)} | Items: {len(items)} | User-Item pairs: {len(agg)}")
    print(f"Events rows: {len(events)} | Onboarding rows: {len(onboarding)}")

    # Build id->index mappings
    user_id_to_idx = {uid: idx for idx, uid in enumerate(users)}
    movie_id_to_idx = {mid: idx for idx, mid in enumerate(items)}

    # Build sparse matrix (users x items)
    row = np.empty(len(agg), dtype=np.int32)
    col = np.empty(len(agg), dtype=np.int32)
    data = np.empty(len(agg), dtype=np.float32)

    for k, ((uid, mid), w) in enumerate(agg.items()):
        row[k] = user_id_to_idx[uid]
        col[k] = movie_id_to_idx[mid]
        data[k] = float(w)

    mat = coo_matrix((data, (row, col)), shape=(len(users), len(items))).tocsr()

 

    model = AlternatingLeastSquares(
        factors=FACTORS,
        regularization=REGULARIZATION,
        iterations=ITERATIONS,
        random_state=42,
    )

    # Train
    model.fit(mat.T)



    # Save factors
    # Swap because we trained on mat.T
    np.save(os.path.join(ART_DIR, "user_factors.npy"), model.item_factors.astype(np.float32))
    np.save(os.path.join(ART_DIR, "item_factors.npy"), model.user_factors.astype(np.float32))


    
    # Save mappings
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
    print("Files: user_factors.npy, item_factors.npy, user_id_to_idx.json, movie_id_to_idx.json, meta.json")


if __name__ == "__main__":
    main()
