from backend.utils.cf_model import CFModel
import pandas as pd
import pickle
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "datasets"
MODELS_DIR = PROJECT_ROOT / "backend/models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Load ratings
ratings = pd.read_csv(DATA_DIR / "ratings.csv")

# Initialize CFModel (this builds the user-item matrix and computes similarities)
cf_model = CFModel(ratings)

# Save model
with open(MODELS_DIR / "cf.pkl", "wb") as f:
    pickle.dump(cf_model, f)

print("CF model saved at:", MODELS_DIR / "cf.pkl")
