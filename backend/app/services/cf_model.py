# backend/utils/cf_model.py
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from scipy.sparse import coo_matrix, csr_matrix

class CFModel:
    """
    Memory-efficient Collaborative Filtering model (Item-Based)
    Computes item-item similarity from user ratings in batches
    and provides user-specific recommendations.
    """

    def __init__(self, ratings_df, top_n_sim=50, batch_size=500):
        self.ratings = ratings_df.copy()
        self.top_n_sim = top_n_sim
        self.batch_size = batch_size

        # Encode users and movies as contiguous integers
        self.user_cat = self.ratings['userId'].astype('category')
        self.movie_cat = self.ratings['movieId'].astype('category')
        self.user_ids = self.user_cat.cat.categories
        self.movie_ids = self.movie_cat.cat.categories

        self.ratings['user_idx'] = self.user_cat.cat.codes
        self.ratings['movie_idx'] = self.movie_cat.cat.codes

        # Create sparse user-item matrix
        self.user_item_matrix = coo_matrix(
            (self.ratings['rating'], (self.ratings['movie_idx'], self.ratings['user_idx'])),
            shape=(len(self.movie_ids), len(self.user_ids))
        ).tocsr()

        # Map between indices and movieIds
        self.idx_to_movieid = dict(enumerate(self.movie_ids))
        self.movieid_to_idx = {mid: idx for idx, mid in self.idx_to_movieid.items()}

        # Precompute top-N similar movies
        self.similar_movies = self._compute_similarity()

    def _compute_similarity(self):
        """
        Compute top-N item-item similarities in batches.
        """
        sim_movies = {}
        num_movies = self.user_item_matrix.shape[0]

        for start in range(0, num_movies, self.batch_size):
            end = min(start + self.batch_size, num_movies)
            batch = self.user_item_matrix[start:end]
            batch_sim = cosine_similarity(batch, self.user_item_matrix)

            for i in range(batch_sim.shape[0]):
                movie_idx = start + i
                top_idx = batch_sim[i].argsort()[::-1][1:self.top_n_sim+1]  # exclude self
                sim_movies[self.idx_to_movieid[movie_idx]] = [self.idx_to_movieid[j] for j in top_idx]

            print(f"Processed {end}/{num_movies} movies for CF similarity")

        return sim_movies

    def get_top_similar_movies(self, movie_id, top_n=10):
        return self.similar_movies.get(movie_id, [])[:top_n]

    def get_recommendations_for_user(self, user_id, top_n=10):
        user_ratings = self.ratings[self.ratings['userId'] == user_id]
        liked_movies = user_ratings[user_ratings['rating'] >= 4.0]['movieId'].tolist()
        if not liked_movies:
            return {}

        rec_scores = {}
        for m in liked_movies:
            for sim in self.get_top_similar_movies(m, top_n=top_n*5):
                rec_scores[sim] = rec_scores.get(sim, 0) + 1

        # Remove already rated movies
        for m in liked_movies:
            rec_scores.pop(m, None)

        return dict(sorted(rec_scores.items(), key=lambda x: x[1], reverse=True)[:top_n])
