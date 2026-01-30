from backend.app.core.model_loader import hybrid_model, movies_df

def get_recommendations(user_id: int, top_k: int):
    """
    Returns top-K recommendations with metadata for API.
    """
    # Step 1: get raw scores from hybrid model
    recs = hybrid_model.recommend(user_id, top_n=top_k)

    # Step 2: map IDs -> metadata
    recs_list = []
    for movie_id, score in recs.items():
        movie_row = movies_df.loc[movies_df['movieId'] == movie_id]
        if movie_row.empty:
            continue
        movie = movie_row.iloc[0]
        recs_list.append({
            "movie_id": movie_id,
            "title": movie['title'],
            "genres": movie.get('genres', ''),
            "year": movie.get('year', ''),
            "image_url": movie.get("image_url", "https://example.com/placeholder.jpg"),
            "description": movie.get('description', ''),
            "score": float(score)
        })

    return recs_list
