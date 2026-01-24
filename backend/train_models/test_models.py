import pickle

# -----------------------
# Load models
# -----------------------
with open("backend/models/cbf.pkl", "rb") as f:
    cbf_model = pickle.load(f)

with open("backend/models/cf.pkl", "rb") as f:
    cf_model = pickle.load(f)

# -----------------------
# Define user and top-N
# -----------------------
user_id = 1
top_n = 10

# -----------------------
# CBF recommendations
# -----------------------
recs_cbf = cbf_model.get_recommendations_for_user(user_id, top_n=top_n)
print(f"\nCBF Recommendations for user {user_id}:")
print(recs_cbf)

# -----------------------
# CF recommendations
# -----------------------
recs_cf = cf_model.get_recommendations_for_user(user_id, top_n=top_n)
print(f"\nCF Recommendations for user {user_id}:")
print(recs_cf)

# -----------------------
# Hybrid recommendations
# -----------------------
# Simple weighted merge
w_cbf = 0.6
w_cf = 0.4
hybrid_recs = {}

# Add CBF
for movie, score in recs_cbf.items():
    hybrid_recs[movie] = hybrid_recs.get(movie, 0) + score * w_cbf

# Add CF
for movie, score in recs_cf.items():
    hybrid_recs[movie] = hybrid_recs.get(movie, 0) + score * w_cf

# Sort top-N
hybrid_top = dict(sorted(hybrid_recs.items(), key=lambda x: x[1], reverse=True)[:top_n])
print(f"\nHybrid Recommendations for user {user_id}:")
print(hybrid_top)
