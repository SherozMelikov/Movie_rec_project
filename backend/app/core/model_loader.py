import pickle
from pathlib import Path
import pandas as pd
from backend.app.services.hybrid_model import HybridRecommender

BASE_DIR = Path(__file__).resolve().parents[3]  # Movie_rec_project/
MODELS_DIR = BASE_DIR / "backend/app/models_store"

# Load pickles
with open(MODELS_DIR / "cbf.pkl", "rb") as f:
    cbf_model = pickle.load(f)

with open(MODELS_DIR / "cf.pkl", "rb") as f:
    cf_model = pickle.load(f)

# Combine into hybrid
hybrid_model = HybridRecommender(cbf_model, cf_model)

# Load movie metadata
movies_df = pd.read_csv(BASE_DIR / "datasets/movies.csv")
