##pytest tests/integration/test_rating_api.py -v
from app.db.models import User, Movie, Rating
from app.core.security import hash_password, create_access_token


def test_rate_movie_stores_rating_successfully(client, db_session):
    # Arrange: create a user
    user = User(
        username="rate_user_tc08",
        email="rate_user_tc08@example.com",
        password_hash=hash_password("Password123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Arrange: create a movie
    movie = Movie(
        movie_id=1,
        title="Inception",
        genres="Action|Sci-Fi",
    )
    db_session.add(movie)
    db_session.commit()

    # Arrange: create auth token
    token = create_access_token({"user_id": user.user_id})
    headers = {"Authorization": f"Bearer {token}"}

    # Act: submit rating
    response = client.put(
        "/ratings/1",
        headers=headers,
        json={"score": 5},
    )

    # Assert: API response
    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 5

    # Assert: rating row stored in DB
    rating = (
        db_session.query(Rating)
        .filter(Rating.user_id == user.user_id, Rating.movie_id == 1)
        .first()
    )
    assert rating is not None
    assert rating.score == 5