# import os
# import json
# from collections import defaultdict

# import joblib
# from sqlalchemy import text

# from lightfm import LightFM
# from lightfm.data import Dataset

# from app.db.database import SessionLocal

# ART_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts", "lightfm")
# os.makedirs(ART_DIR, exist_ok=True)

# EPOCHS = 3
# NUM_THREADS = 1  # Windows + no OpenMP => keep 1 thread


# def event_weight(event_type: str, rating_value):
#     """
#     Convert events into numeric weights.
#     Important: views are very frequent, so keep them low.
#     """
#     if event_type == "view":
#         return 0.25
#     if event_type == "like":
#         return 4.0
#     if event_type == "rate":
#         # map 1..5 to weights (implicit style)
#         mapping = {1: 0.2, 2: 0.5, 3: 1.0, 4: 2.0, 5: 3.0}
#         return float(mapping.get(int(rating_value or 3), 1.0))
#     return 0.0


# def onboarding_weight():
#     # Treat onboarding picks as strong positive implicit feedback
#     return 3.0


# def load_events_and_onboarding():
#     db = SessionLocal()
#     try:
#         events = db.execute(text("""
#             SELECT user_id, movie_id, event_type, rating_value
#             FROM events
#         """)).fetchall()

#         onboarding = db.execute(text("""
#             SELECT user_id, movie_id
#             FROM user_onboarding_movies
#         """)).fetchall()

#         return events, onboarding
#     finally:
#         db.close()


# def main():
#     events, onboarding = load_events_and_onboarding()

#     if not events and not onboarding:
#         raise RuntimeError("No events or onboarding interactions found in DB.")

#     # Aggregate weights per (user_id, movie_id)
#     agg = defaultdict(float)
#     users_set = set()
#     items_set = set()

#     # 1) Events
#     for user_id, movie_id, event_type, rating_value in events:
#         w = event_weight(event_type, rating_value)
#         if w <= 0:
#             continue

#         u = int(user_id)
#         i = int(movie_id)

#         # Prevent repeated views from dominating:
#         # - views: keep max (0.25)
#         # - likes/ratings: add
#         if event_type == "view":
#             agg[(u, i)] = max(agg[(u, i)], w)
#         else:
#             agg[(u, i)] += w

#         users_set.add(u)
#         items_set.add(i)

#     # 2) Onboarding picked movies (strong positive)
#     ow = onboarding_weight()
#     for user_id, movie_id in onboarding:
#         u = int(user_id)
#         i = int(movie_id)
#         agg[(u, i)] += ow
#         users_set.add(u)
#         items_set.add(i)

#     users = sorted(users_set)
#     items = sorted(items_set)

#     print(f"Users: {len(users)} | Items: {len(items)} | User-Item pairs: {len(agg)}")
#     print(f"Events rows: {len(events)} | Onboarding rows: {len(onboarding)}")

#     # Build LightFM Dataset and interactions
#     dataset = Dataset()
#     dataset.fit(users=users, items=items)

#     interactions, weights = dataset.build_interactions(
#         ((u, i, w) for (u, i), w in agg.items())
#     )

#     # Train model
#     model = LightFM(
#         loss="warp",          # best default for implicit ranking
#         no_components=64,
#         learning_rate=0.05,
#         user_alpha=1e-6,
#         item_alpha=1e-6,
#         random_state=42,
#     )

#     model.fit(
#         interactions,
#         sample_weight=weights,
#         epochs=EPOCHS,
#         num_threads=NUM_THREADS,
#         verbose=True,
#     )

#     # Save artifacts
#     model_path = os.path.join(ART_DIR, "model.joblib")
#     dataset_path = os.path.join(ART_DIR, "dataset.joblib")
#     meta_path = os.path.join(ART_DIR, "meta.json")

#     joblib.dump(model, model_path)
#     joblib.dump(dataset, dataset_path)

#     meta = {
#         "loss": "warp",
#         "no_components": 64,
#         "epochs": EPOCHS,
#         "learning_rate": 0.05,
#         "users": len(users),
#         "items": len(items),
#         "pairs": len(agg),
#         "event_rows": len(events),
#         "onboarding_rows": len(onboarding),
#         "onboarding_weight": ow,
#         "weights": {
#             "view": 0.25,
#             "like": 4.0,
#             "rate_map": {1: 0.2, 2: 0.5, 3: 1.0, 4: 2.0, 5: 3.0},
#         },
#         "notes": "views use max() per (user,item) to avoid view spam dominating",
#     }

#     with open(meta_path, "w", encoding="utf-8") as f:
#         json.dump(meta, f, indent=2)

#     print("✅ Saved LightFM artifacts to:", ART_DIR)
#     print("Files:", os.path.basename(model_path), os.path.basename(dataset_path), os.path.basename(meta_path))


# if __name__ == "__main__":
#     main()
