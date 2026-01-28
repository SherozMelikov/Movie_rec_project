from fastapi import APIRouter
from app.schemas.recommendation import (
    RecommendRequest,
    RecommendationResponse
)
from app.core.model_loader import hybrid_model, movies_df

router = APIRouter()

@router.post("/", response_model=RecommendationResponse)
def recommend_movies(request: RecommendRequest):
    recs = hybrid_model.recommend(request.user_id, top_n=request.top_k)

    recs_list = []
    for movie_id, score in recs.items():
        title_row = movies_df.loc[movies_df['movieId'] == movie_id, 'title']
        title = title_row.values[0] if not title_row.empty else "Unknown Title"

        recs_list.append({
            "movie_id": movie_id,
            "title": title,
            "score": float(score)
        })

    return {"recommendations": recs_list}
