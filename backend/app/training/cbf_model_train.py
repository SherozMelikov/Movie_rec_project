import pickle
import pandas as pd
from pathlib import Path

from app.services.cbf_model import DynamicCBF

BASE_DIR = Path(__file__).resolve().parents[3]

DATA_DIR = BASE_DIR / "datasets"
MODELS_DIR = BASE_DIR / "backend/app/models_store"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

print("Loading data...")
movies = pd.read_csv(DATA_DIR / "movies.csv")
tags = pd.read_csv(DATA_DIR / "tags.csv")
ratings = pd.read_csv(DATA_DIR / "ratings.csv")

print("Training CBF model...")
cbf_model = DynamicCBF(movies, tags, ratings)

model_path = MODELS_DIR / "cbf.pkl"
with open(model_path, "wb") as f:
    pickle.dump(cbf_model, f)

print(f"✅ CBF model saved at: {model_path}")
