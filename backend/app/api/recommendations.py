from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.core.model_loader import hybrid_model, movies_df
from backend.app.schemas.schemas import RecommendationItem, RecommendationList

router = APIRouter()

@router.get("/{user_id}", response_model=RecommendationList)
def get_recommendations(user_id: int, top_k: int = Query(10, gt=0), db: Session = Depends(get_db)):
    # Step 1: get user ratings from DB
    from backend.app.db.models import Rating
    user_ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
    user_history = {r.movie_id: r.rating for r in user_ratings}

    # Step 2: generate recommendations
    recs = hybrid_model.recommend(user_id=user_id, top_n=top_k)

    # Step 3: map IDs to movie info
    rec_list = []
    for movie_id, score in recs.items():
        movie_row = movies_df.loc[movies_df['movieId'] == movie_id]
        if movie_row.empty:
            continue
        movie = movie_row.iloc[0]
        rec_list.append(
            RecommendationItem(
                movie_id=movie_id,
                title=movie['title'],
                genres=movie['genres'],
                year=movie.get('year'),
                poster_url=movie.get('poster_url', "https://example.com/placeholder.jpg"),
                plot=movie.get('plot', ''),
                score=float(score)
            )
        )

    return RecommendationList(user_id=user_id, recommendations=rec_list)
