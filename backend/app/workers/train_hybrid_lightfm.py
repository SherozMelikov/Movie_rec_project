# import numpy as np
# import pandas as pd
# from pathlib import Path
# import pickle
# from lightfm import LightFM
# from lightfm.data import Dataset
# from lightfm.evaluation import precision_at_k, auc_score
# from sqlalchemy.orm import Session

# from app.db.database import SessionLocal
# from app.db.models import Rating, Like, Movie

# # ---------- CONFIG ----------
# BASE_DIR = Path(__file__).resolve().parents[3]
# MODELS_DIR = BASE_DIR / "backend/app/models_store"
# MODELS_DIR.mkdir(parents=True, exist_ok=True)

# MODEL_PATH = MODELS_DIR / "hybrid_model.pkl"
# DATASET_PATH = MODELS_DIR / "hybrid_dataset.pkl"

# EPOCHS = 15
# TOP_K = 3


# # ---------- DATA PREPARATION ----------
# def prepare_data(db: Session):
#     ratings = pd.DataFrame(
#         db.query(Rating.user_id, Rating.movie_id, Rating.score).all(),
#         columns=["user_id", "movie_id", "score"],
#     )
#     ratings["score"] = ratings["score"] / 5.0

#     likes = pd.DataFrame(
#         db.query(Like.user_id, Like.movie_id).all(),
#         columns=["user_id", "movie_id"],
#     )
#     likes["score"] = 1.0

#     interactions_df = pd.concat([ratings, likes], ignore_index=True)

#     print("Users:", interactions_df.user_id.nunique())
#     print("Movies:", interactions_df.movie_id.nunique())
#     print("Interactions:", len(interactions_df))

#     return interactions_df


# # ---------- MAIN ----------
# if __name__ == "__main__":
#     try:
#         db = SessionLocal()

#         print("Preparing data...")
#         interactions_df = prepare_data(db)

#         # ---------- Collect movies & genres ----------
#         movies = db.query(Movie.movie_id, Movie.genres).all()

#         all_movies = [m.movie_id for m in movies]

#         all_genres = set()
#         for m in movies:
#             for g in m.genres.split("|"):
#                 all_genres.add(g.strip())

#         print("Total genres:", len(all_genres))

#         # ---------- Prepare LightFM dataset ----------
#         print("Preparing LightFM dataset...")
#         dataset = Dataset()
#         dataset.fit(
#             users=interactions_df["user_id"].unique(),
#             items=all_movies,
#             item_features=list(all_genres),  # ⭐ CRITICAL
#         )

#         # ---------- Build interactions ----------
#         print("Building interactions matrix...")
#         interactions, _ = dataset.build_interactions(
#             (
#                 row.user_id,
#                 row.movie_id,
#                 row.score,
#             )
#             for row in interactions_df.itertuples()
#         )

#         # ---------- Build item features ----------
#         print("Building item features...")
#         item_features = dataset.build_item_features(
#             (
#                 m.movie_id,
#                 [g.strip() for g in m.genres.split("|")],
#             )
#             for m in movies
#         )

#         # ---------- Train model ----------
#         print("Training hybrid LightFM model...")
#         model = LightFM(
#             loss="warp",
#             learning_rate=0.01,
#             no_components=10,
#             user_alpha=1e-6,
#             item_alpha=1e-6,
#         )

#         model.fit(
#             interactions,
#             item_features=item_features,
#             epochs=EPOCHS,
#             num_threads=1,
#             verbose=True,  
#         )


#         print("Training complete.")

#         # ---------- Save ----------
#         with open(MODEL_PATH, "wb") as f:
#             pickle.dump(model, f)

#         with open(DATASET_PATH, "wb") as f:
#             pickle.dump(dataset, f)

#         print("✅ Model and dataset saved.")

#         # ---------- Test recommendations ----------
#         print("\nTop recommendations:")
#         user_map, _, item_map, _ = dataset.mapping()
#         reverse_item_map = {v: k for k, v in item_map.items()}

#         for user_id in interactions_df.user_id.unique():
#             user_x = user_map[user_id]

#             scores = model.predict(
#                 user_x,
#                 np.arange(len(item_map)),
#                 item_features=item_features,
#             )

#             top_items = np.argsort(-scores)[:TOP_K]
#             recommended = [reverse_item_map[i] for i in top_items]

#             print(f"User {user_id}: {recommended}")

#         # ---------- Evaluation ----------
#         print("\nEvaluating model...")
#         prec = precision_at_k(
#             model, interactions, item_features=item_features, k=TOP_K
#         ).mean()
#         auc = auc_score(
#             model, interactions, item_features=item_features
#         ).mean()

#         print(f"Precision@{TOP_K}: {prec:.4f}")
#         print(f"AUC: {auc:.4f}")

#     except Exception as e:
#         print("❌ Error:", e)
