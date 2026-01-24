from pathlib import Path
import pickle
from fastapi import FastAPI

app = FastAPI()

# Correct path to the model
MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "cbf.pkl"

with open(MODEL_PATH, "rb") as f:
    cbf_model = pickle.load(f)

@app.get("/recommend/cbf/{user_id}")
def recommend_cbf(user_id: int, top_n: int = 10):
    recs = cbf_model.get_recommendations_for_user(user_id, top_n=top_n)
    return {"recommendations": recs}
