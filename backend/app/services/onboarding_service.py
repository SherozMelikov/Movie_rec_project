from __future__ import annotations

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db.models import Movie, UserOnboardingMovie
from app.schemas.schemas import OnboardingOut


class OnboardingService:
    def save_onboarding(
        self,
        db: Session,
        user_id: int,
        picked_movie_ids: list[int],
    ) -> OnboardingOut:

        # validate movies exist
        if picked_movie_ids:
            rows = (
                db.query(Movie.movie_id)
                .filter(Movie.movie_id.in_(picked_movie_ids))
                .all()
            )
            found = {r[0] for r in rows}
            missing = [mid for mid in picked_movie_ids if mid not in found]
            if missing:
                raise HTTPException(status_code=400, detail=f"Invalid movie_ids: {missing[:10]}")

        # replace picked movies
        db.query(UserOnboardingMovie).filter_by(user_id=user_id).delete()

        db.bulk_save_objects([
            UserOnboardingMovie(user_id=user_id, movie_id=int(mid))
            for mid in picked_movie_ids
        ])

        db.commit()

        return OnboardingOut(
            user_id=user_id,
            picked_movie_ids=picked_movie_ids,
        )

    def get_my_onboarding(self, db: Session, user_id: int) -> OnboardingOut | None:
        picked = db.query(UserOnboardingMovie.movie_id).filter_by(user_id=user_id).all()
        picked_ids = [int(r[0]) for r in picked]

        if not picked_ids:
            return None

        return OnboardingOut(
            user_id=user_id,
            picked_movie_ids=picked_ids,
        )


onboarding_service = OnboardingService()