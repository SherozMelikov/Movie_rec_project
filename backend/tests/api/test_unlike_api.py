
##pytest tests/integration/test_unlike_api.py -v
from app.db.models import User, Movie, Like
from app.core.security import hash_password, create_access_token


def test_unlike_movie_removes_like_successfully(client, db_session):
    # Arrange: create a user
    user = User(
        username="unlike_user_tc07",
        email="unlike_user_tc07@example.com",
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

    # Arrange: create an existing like
    like = Like(user_id=user.user_id, movie_id=movie.movie_id)
    db_session.add(like)
    db_session.commit()

    # Arrange: create auth token
    token = create_access_token({"user_id": user.user_id})
    headers = {"Authorization": f"Bearer {token}"}

    # Act: unlike the movie
    response = client.delete("/likes/1", headers=headers)

    # Assert: API response
    assert response.status_code == 204
    assert response.content == b""

    # Assert: like row removed from DB
    deleted_like = (
        db_session.query(Like)
        .filter(Like.user_id == user.user_id, Like.movie_id == 1)
        .first()
    )
    assert deleted_like is None