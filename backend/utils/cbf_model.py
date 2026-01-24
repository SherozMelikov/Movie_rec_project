import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MultiLabelBinarizer, normalize
from sklearn.metrics.pairwise import cosine_similarity
from scipy.sparse import hstack, csr_matrix

class CBFModel:
    """
    Content-Based Filtering model.
    Combines genres and tags, computes cosine similarity in batches,
    and provides user-specific recommendations.
    """

    def __init__(self, movies_df, tags_df, ratings_df, alpha=0.7, beta=0.3, top_n_sim=50):
        self.movies = movies_df.copy()
        self.ratings = ratings_df.copy()

        # Merge aggregated tags
        tags_df['tag'] = tags_df['tag'].fillna('')
        tags_agg = tags_df.groupby('movieId')['tag'].agg(' '.join).reset_index()
        self.movies = self.movies.merge(tags_agg, on='movieId', how='left')
        self.movies['tag'] = self.movies['tag'].fillna('')

        # Feature matrix: genres + tags
        self.movies['genre_text'] = self.movies['genres'].fillna('').str.replace('|', ' ')
        self.movies['content'] = (self.movies['genre_text'] + ' ' + self.movies['tag']).str.strip()

        # TF-IDF for tags
        tfidf = TfidfVectorizer(min_df=2, max_df=0.9)
        tfidf_matrix = normalize(tfidf.fit_transform(self.movies['tag'])) * beta

        # One-hot encode genres
        mlb = MultiLabelBinarizer()
        genre_matrix = normalize(mlb.fit_transform(self.movies['genres'].str.split('|'))) * alpha

        # Concatenate features
        self.item_matrix = csr_matrix(hstack([genre_matrix, tfidf_matrix]))

        # Map movieId <-> index
        self.movieid_to_idx = pd.Series(self.movies.index.values, index=self.movies['movieId']).to_dict()
        self.idx_to_movieid = pd.Series(self.movies['movieId'].values, index=self.movies.index).to_dict()

        # Precompute top-N similar movies
        self.top_n_sim = top_n_sim
        self.similar_movies = self._compute_similarity()

    def _compute_similarity(self):
        """
        Compute top-N similar movies in batches.
        Prevents memory overload for large datasets.
        """
        sim_movies = {}
        batch_size = 500  # adjust based on your RAM
        num_movies = self.item_matrix.shape[0]

        for start in range(0, num_movies, batch_size):
            end = min(start + batch_size, num_movies)
            batch_sim = cosine_similarity(self.item_matrix[start:end], self.item_matrix)

            for i in range(batch_sim.shape[0]):
                movie_id = self.movies.iloc[start + i]['movieId']
                top_idx = batch_sim[i].argsort()[::-1][1:self.top_n_sim+1]  # global indices
                sim_movies[movie_id] = [self.idx_to_movieid[j] for j in top_idx]

            print(f"Processed {end}/{num_movies} movies")

        return sim_movies

    def get_top_similar_movies(self, movie_id, top_n=10):
        """Return top-N similar movies for a given movie."""
        return self.similar_movies.get(movie_id, [])[:top_n]

    def get_recommendations_for_user(self, user_id, top_n=10):
        """
        Recommend movies for a user by aggregating similar movies
        from the movies they rated highly (>= 4.0).
        """
        user_movies = self.ratings[(self.ratings['userId'] == user_id) & (self.ratings['rating'] >= 4.0)]
        liked_movies = user_movies['movieId'].tolist()
        if not liked_movies:
            return {}

        rec_scores = {}
        for m in liked_movies:
            for sim in self.get_top_similar_movies(m, top_n=top_n*5):
                rec_scores[sim] = rec_scores.get(sim, 0) + 1

        # Remove already rated movies
        for m in liked_movies:
            rec_scores.pop(m, None)

        # Return top-N recommendations
        return dict(sorted(rec_scores.items(), key=lambda x: x[1], reverse=True)[:top_n])
