class HybridRecommender:
    def __init__(self, cbf_model, cf_model, w_cbf=0.6, w_cf=0.4):
        self.cbf = cbf_model
        self.cf = cf_model
        self.w_cbf = w_cbf
        self.w_cf = w_cf

    def recommend(self, user_id, top_n=10):
        # Step 1: get raw recommendations
        cbf_recs = self.cbf.get_recommendations_for_user(user_id, top_n*2)
        cf_recs = self.cf.get_recommendations_for_user(user_id, top_n*2)

        # Step 2: normalize scores
        def normalize(scores):
            if not scores: return {}
            max_score = max(scores.values())
            return {k: v / max_score for k, v in scores.items()}

        cbf_recs = normalize(cbf_recs)
        cf_recs = normalize(cf_recs)

        # Step 3: merge weighted
        hybrid_scores = {}
        for movie_id, score in cbf_recs.items():
            hybrid_scores[movie_id] = hybrid_scores.get(movie_id, 0) + score * self.w_cbf
        for movie_id, score in cf_recs.items():
            hybrid_scores[movie_id] = hybrid_scores.get(movie_id, 0) + score * self.w_cf

        # Step 4: sort top-N
        top_hybrid = dict(sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)[:top_n])

        # Step 5: optional: map to titles for frontend
        top_hybrid_with_titles = [
            {
                "movie_id": mid,
                "title": self.cbf.movies.loc[self.cbf.movieid_to_idx[mid], "title"],
                "score": score
            }
            for mid, score in top_hybrid.items()
        ]
        return top_hybrid_with_titles
