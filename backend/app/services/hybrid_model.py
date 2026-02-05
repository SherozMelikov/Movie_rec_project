from app.services.cbf_model import DynamicCBF
from app.services.cf_model import DynamicCF


class DynamicHybridRecommender:
    def __init__(self, cbf_model: DynamicCBF, cf_model: DynamicCF, w_cbf=0.6, w_cf=0.4):
        self.cbf = cbf_model
        self.cf = cf_model
        self.w_cbf = w_cbf
        self.w_cf = w_cf

    def recommend(self, user_id, user_ratings, top_n=10):
        # user_ratings: DataFrame of only this user's ratings
        cbf_recs = self.cbf.recommend_for_user(user_ratings, top_n*2)
        cf_recs = self.cf.recommend_for_user(user_id, top_n*2)

        def normalize(scores):
            if not scores:
                return {}
            max_score = max(scores.values())
            return {k: v / max_score for k, v in scores.items()}

        cbf_recs = normalize(cbf_recs)
        cf_recs = normalize(cf_recs)

        hybrid_scores = {}
        for movie_id, score in cbf_recs.items():
            hybrid_scores[movie_id] = hybrid_scores.get(movie_id, 0) + score * self.w_cbf
        for movie_id, score in cf_recs.items():
            hybrid_scores[movie_id] = hybrid_scores.get(movie_id, 0) + score * self.w_cf

        return dict(sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)[:top_n])
