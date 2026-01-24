class HybridRecommender:
    def __init__(self, cbf_model, cf_model, w_cbf=0.6, w_cf=0.4):
        self.cbf = cbf_model
        self.cf = cf_model
        self.w_cbf = w_cbf
        self.w_cf = w_cf

    def recommend(self, user_id, top_n=10):
        cbf_recs = self.cbf.get_recommendations_for_user(user_id, top_n=top_n * 2)
        cf_recs = self.cf.get_recommendations_for_user(user_id, top_n=top_n * 2)

        hybrid_scores = {}

        # Normalize and merge
        for movie_id, score in cbf_recs.items():
            hybrid_scores[movie_id] = hybrid_scores.get(movie_id, 0) + score * self.w_cbf

        for movie_id, score in cf_recs.items():
            hybrid_scores[movie_id] = hybrid_scores.get(movie_id, 0) + score * self.w_cf

        # Sort and return top-N
        return dict(
            sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
        )
