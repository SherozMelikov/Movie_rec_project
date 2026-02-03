# backend/app/api/recommendations.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.db.database import get_db
from backend.app.core.model_loader import hybrid_model, movies_df
from backend.app.schemas.schemas import RecommendationItem, RecommendationList
from backend.app.db.models import Rating

router = APIRouter()

# -------------------------------
# 1️⃣ Top Picks - personalized
# -------------------------------
@router.get("/top-picks", response_model=RecommendationList)
def top_picks(user_id: int, top_k: int = 10, db: Session = Depends(get_db)):
    recs = hybrid_model.recommend(user_id=user_id, top_n=top_k)
    rec_list = []
    for movie_id, score in recs.items():
        movie_row = movies_df.loc[movies_df['movieId'] == movie_id]
        if movie_row.empty:
            continue
        movie = movie_row.iloc[0]
        rec_list.append(RecommendationItem(
            movie_id=movie_id,
            title=movie['title'],
            genres=movie['genres'],
            year=movie.get('year'),
            poster_url=movie.get('poster_url', "https://example.com/placeholder.jpg"),
            plot=movie.get('plot', ''),
            score=float(score)
        ))
    return RecommendationList(user_id=user_id, recommendations=rec_list)

# -------------------------------
# 2️⃣ Trending - globally popular
# -------------------------------
@router.get("/trending", response_model=list[RecommendationItem])
def trending(top_k: int = 10, db: Session = Depends(get_db)):
    trending_movies = (
        db.query(Rating.movie_id, func.avg(Rating.rating).label("avg_rating"))
        .group_by(Rating.movie_id)
        .order_by(func.avg(Rating.rating).desc())
        .limit(top_k)
        .all()
    )

    rec_list = []
    for movie_id, avg_rating in trending_movies:
        movie_row = movies_df.loc[movies_df['movieId'] == movie_id]
        if movie_row.empty:
            continue
        movie = movie_row.iloc[0]
        rec_list.append(RecommendationItem(
            movie_id=movie_id,
            title=movie['title'],
            genres=movie['genres'],
            year=movie.get('year'),
            poster_url=movie.get('poster_url', "https://example.com/placeholder.jpg"),
            plot=movie.get('plot', ''),
            score=float(avg_rating)
        ))
    return rec_list

# -------------------------------
# 3️⃣ Because You Rated - personalized
# -------------------------------
@router.get("/because-you-rated", response_model=list[RecommendationItem])
def because_you_rated(user_id: int, top_k: int = 10, db: Session = Depends(get_db)):
    # Get all movies the user has rated
    user_ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
    if not user_ratings:
        return []

    # Collect similar movies
    similar_movies = []
    rated_movie_ids = set()
    for r in user_ratings:
        rated_movie_ids.add(r.movie_id)
        movie_row = movies_df.loc[movies_df['movieId'] == r.movie_id]
        if movie_row.empty:
            continue
        movie = movie_row.iloc[0]
        target_genres = set(movie['genres'].split("|"))

        for _, m in movies_df.iterrows():
            if m['movieId'] in rated_movie_ids:
                continue
            genres = set(m['genres'].split("|"))
            similarity = len(target_genres & genres) / len(target_genres | genres)
            if similarity > 0:
                similar_movies.append((m['movieId'], similarity, m))

    # Aggregate to avoid duplicates (keep max similarity)
    movie_dict = {}
    for m_id, sim, m in similar_movies:
        if m_id not in movie_dict or sim > movie_dict[m_id][0]:
            movie_dict[m_id] = (sim, m)

    # Sort by similarity descending
    sorted_movies = sorted(movie_dict.items(), key=lambda x: x[1][0], reverse=True)[:top_k]

    # Build response
    rec_list = [
        RecommendationItem(
            movie_id=m_id,
            title=m['title'],
            genres=m['genres'],
            year=m.get('year'),
            poster_url=m.get('poster_url', "https://example.com/placeholder.jpg"),
            plot=m.get('plot', ''),
            score=sim
        )
        for m_id, (sim, m) in sorted_movies
    ]

    return rec_list

# -------------------------------
# 4️⃣ Genre-based
# -------------------------------
@router.get("/genre", response_model=list[RecommendationItem])
def genre_movies(genre: str, user_id: int = None, top_k: int = 10):
    filtered = movies_df[movies_df['genres'].str.contains(genre, case=False, na=False)]
    
    rec_list = []
    for _, movie in filtered.iterrows():
        score = 0
        if user_id:
            score = hybrid_model.predict(user_id, movie['movieId'])
        rec_list.append(RecommendationItem(
            movie_id=movie['movieId'],
            title=movie['title'],
            genres=movie['genres'],
            year=movie.get('year'),
            poster_url=movie.get('poster_url', "https://example.com/placeholder.jpg"),
            plot=movie.get('plot', ''),
            score=float(score)
        ))
    
    rec_list.sort(key=lambda x: x.score, reverse=True)
    return rec_list[:top_k]

# -------------------------------
# 5️⃣ New Releases
# -------------------------------
@router.get("/new-releases", response_model=list[RecommendationItem])
def new_releases(top_k: int = 10, db: Session = Depends(get_db)):
    merged = movies_df.copy()
    
    # Merge average rating for score
    avg_ratings = db.query(Rating.movie_id, func.avg(Rating.rating).label("avg_rating"))\
        .group_by(Rating.movie_id).all()
    rating_dict = {m_id: avg for m_id, avg in avg_ratings}
    merged['score'] = merged['movieId'].map(rating_dict).fillna(0)

    merged = merged.sort_values(by='year', ascending=False)
    
    rec_list = [
        RecommendationItem(
            movie_id=row['movieId'],
            title=row['title'],
            genres=row['genres'],
            year=row.get('year'),
            poster_url=row.get('poster_url', "https://example.com/placeholder.jpg"),
            plot=row.get('plot', ''),
            score=float(row['score'])
        )
        for _, row in merged.head(top_k).iterrows()
    ]
    return rec_list
