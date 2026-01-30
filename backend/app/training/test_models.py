import pickle
from backend.app.services.hybrid_model import HybridRecommender

# Load saved models
with open("backend/models/cbf.pkl", "rb") as f:
    cbf_model = pickle.load(f)
with open("backend/models/cf.pkl", "rb") as f:
    cf_model = pickle.load(f)

hybrid = HybridRecommender(cbf_model, cf_model)
recs = hybrid.recommend(user_id=1, top_n=10)

for r in recs:
    print(r)
