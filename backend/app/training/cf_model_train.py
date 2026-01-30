import pickle
import pandas as pd
from pathlib import Path

from backend.app.services.cf_model import CFModel

BASE_DIR = Path(__file__).resolve().parents[3]

DATA_DIR = BASE_DIR / "datasets"
MODELS_DIR = BASE_DIR / "backend/app/models_store"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

print("Loading data...")
ratings = pd.read_csv(DATA_DIR / "ratings.csv")

print("Training CF model...")
cf_model = CFModel(ratings)

model_path = MODELS_DIR / "cf.pkl"
with open(model_path, "wb") as f:
    pickle.dump(cf_model, f)

print(f"✅ CF model saved at: {model_path}")
