## pytest tests/integration/test_like_api.py -v
from app.db.models import User, Movie, Like
from app.core.security import hash_password, create_access_token


def test_like_movie_stores_like_successfully(client, db_session):
    # Arrange: create a user
    user = User(
        username="like_user_tc06",
        email="like_user_tc06@example.com",
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

    # Act: like the movie
    response = client.post("/likes/1", headers=headers)

    # Assert: API response
    assert response.status_code == 200
    data = response.json()
    assert data["liked"] is True

    # Assert: like row stored in DB
    like = (
        db_session.query(Like)
        .filter(Like.user_id == user.user_id, Like.movie_id == 1)
        .first()
    )
    assert like is not None