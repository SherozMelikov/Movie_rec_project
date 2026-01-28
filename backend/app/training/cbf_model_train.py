from backend.app.modules.cbf_model import CBFModel
import pandas as pd
import pickle
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "datasets"
MODELS_DIR = PROJECT_ROOT / "backend/models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

movies = pd.read_csv(DATA_DIR / "movies.csv")
tags = pd.read_csv(DATA_DIR / "tags.csv")
ratings = pd.read_csv(DATA_DIR / "ratings.csv")

cbf_model = CBFModel(movies, tags, ratings)

with open(MODELS_DIR / "cbf.pkl", "wb") as f:
    pickle.dump(cbf_model, f)

print("CBF model saved at:", MODELS_DIR / "cbf.pkl")
