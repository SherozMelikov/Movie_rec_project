import pickle
from pathlib import Path
import pandas as pd
from backend.app.services.hybrid_model import HybridRecommender

PROJECT_ROOT = Path(__file__).resolve().parents[3]

with open(PROJECT_ROOT / "backend/app/modules_store/cbf.pkl", "rb") as f:
    cbf_model = pickle.load(f)

with open(PROJECT_ROOT / "backend/app/modules_store/cf.pkl", "rb") as f:
    cf_model = pickle.load(f)

hybrid_model = HybridRecommender(cbf_model, cf_model)

movies_df = pd.read_csv(PROJECT_ROOT / "datasets/movies.csv")
