from scipy.sparse import coo_matrix
from sklearn.metrics.pairwise import cosine_similarity

class DynamicCF:
    def __init__(self, ratings_df, top_n_sim=50):
        self.ratings = ratings_df.copy()
        self.top_n_sim = top_n_sim
        # Create consistent categorical index FIRST
        self.ratings['movie_idx'] = self.ratings['movie_id'].astype('category').cat.codes
        self.ratings['user_idx'] = self.ratings['user_id'].astype('category').cat.codes

        # Now build mapping FROM the categorical codes
        movie_mapping = (
            self.ratings[['movie_id', 'movie_idx']]
            .drop_duplicates()
            .set_index('movie_id')['movie_idx']
        )

        self.movieid_to_idx = movie_mapping.to_dict()
        self.idx_to_movieid = {v: k for k, v in self.movieid_to_idx.items()}


        # Build full sparse user-item matrix
        self.ratings['user_idx'] = self.ratings['user_id'].astype('category').cat.codes
        self.ratings['movie_idx'] = self.ratings['movie_id'].astype('category').cat.codes
        self.user_item_matrix = coo_matrix(
            (self.ratings['rating'], (self.ratings['movie_idx'], self.ratings['user_idx']))
        ).tocsr()

    def recommend_for_user(self, user_id, top_n=10):
        # Get movies this user liked
        user_movies = self.ratings[(self.ratings['user_id'] == user_id) & (self.ratings['rating'] >= 4)]
        liked_movies = user_movies['movie_id'].tolist()
        rec_scores = {}

        # Compute similarity only for liked movies
        for m in liked_movies:
            if m not in self.movieid_to_idx:
                continue
            movie_idx = self.movieid_to_idx[m]
            sim = cosine_similarity(
                self.user_item_matrix[movie_idx], self.user_item_matrix
            ).flatten()
            top_idx = sim.argsort()[::-1][1:top_n*5+1]
            for idx in top_idx:
                rec_movie_id = self.idx_to_movieid[idx]
                if rec_movie_id not in liked_movies:
                    rec_scores[rec_movie_id] = rec_scores.get(rec_movie_id, 0) + sim[idx]
        return dict(sorted(rec_scores.items(), key=lambda x: x[1], reverse=True)[:top_n])
