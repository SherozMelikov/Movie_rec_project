##pytest tests/integration/test_onboarding_api.py -v

from app.db.models import User, Movie
from app.core.security import hash_password, create_access_token


def test_complete_onboarding_saves_preferences_successfully(client, db_session):
    # Arrange: create a user
    user = User(
        username="onboarding_user_tc09",
        email="onboarding_user_tc09@example.com",
        password_hash=hash_password("Password123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Arrange: create movies for onboarding selection
    movies = [
        Movie(movie_id=1, title="Inception", genres="Action|Sci-Fi"),
        Movie(movie_id=2, title="Interstellar", genres="Adventure|Sci-Fi"),
        Movie(movie_id=3, title="The Dark Knight", genres="Action|Crime"),
        Movie(movie_id=4, title="Titanic", genres="Romance|Drama"),
        Movie(movie_id=5, title="Avatar", genres="Adventure|Fantasy"),
    ]
    db_session.add_all(movies)
    db_session.commit()

    # Arrange: auth token
    token = create_access_token({"user_id": user.user_id})
    headers = {"Authorization": f"Bearer {token}"}

    # Act: submit onboarding picks
    response = client.post(
        "/onboarding",
        headers=headers,
        json={
            "picked_movie_ids": [1, 2, 3, 4, 5]
        },
    )

    # Assert: API response
    assert response.status_code == 200

    data = response.json()
    assert data["user_id"] == user.user_id
    assert data["picked_movie_ids"] == [1, 2, 3, 4, 5]