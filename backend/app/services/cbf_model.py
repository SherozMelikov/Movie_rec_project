from sklearn.preprocessing import MultiLabelBinarizer, normalize
from sklearn.metrics.pairwise import cosine_similarity
from scipy.sparse import csr_matrix
import pandas as pd
import numpy as np

class DynamicCBF:
    def __init__(self, movies_df, alpha=1.0, top_n_sim=50):
        self.movies = movies_df.copy()
        self.movies['genres'] = self.movies['genres'].fillna('')
        self.movies['genre_list'] = self.movies['genres'].str.split('|')
        mlb = MultiLabelBinarizer()
        genre_matrix = normalize(mlb.fit_transform(self.movies['genre_list'])) * alpha
        self.item_matrix = csr_matrix(genre_matrix)
        self.movieid_to_idx = pd.Series(self.movies.index.values, index=self.movies['movie_id']).to_dict()
        self.idx_to_movieid = pd.Series(self.movies['movie_id'].values, index=self.movies.index).to_dict()

        # Precompute movie-to-movie similarity
        self.similar_movies = self._compute_similarity(top_n_sim)

    def _compute_similarity(self, top_n_sim):
        sim_movies = {}
        num_movies = self.item_matrix.shape[0]
        batch_size = 500
        for start in range(0, num_movies, batch_size):
            end = min(start + batch_size, num_movies)
            batch_sim = cosine_similarity(self.item_matrix[start:end], self.item_matrix)
            for i in range(batch_sim.shape[0]):
                movie_idx = start + i
                top_idx = batch_sim[i].argsort()[::-1][1:top_n_sim+1]  # skip self
                sim_movies[self.idx_to_movieid[movie_idx]] = [self.idx_to_movieid[j] for j in top_idx]
        return sim_movies

    def recommend_for_user(self, user_ratings: pd.DataFrame, top_n=10):
        # user_ratings: DataFrame with columns ['movie_id', 'rating'] (only this user's ratings)
        liked_movies = user_ratings[user_ratings['rating'] >= 4]['movie_id'].tolist()
        rec_scores = {}
        for m in liked_movies:
            for sim in self.similar_movies.get(m, [])[:top_n*5]:
                rec_scores[sim] = rec_scores.get(sim, 0) + 1
        for m in liked_movies:
            rec_scores.pop(m, None)
        # Return top-N
        return dict(sorted(rec_scores.items(), key=lambda x: x[1], reverse=True)[:top_n])
