##pytest tests/integration/test_movie_details_api.py -v
from app.db.models import Movie, MovieMetadata


def test_get_movie_details_returns_correct_data(client, db_session):
    # Arrange: create a movie
    movie = Movie(
        movie_id=1,
        title="Inception",
        genres="Action|Sci-Fi",
    )
    db_session.add(movie)

    # Optional metadata (since your endpoint uses it)
    metadata = MovieMetadata(
        movie_id=1,
        overview="A mind-bending thriller",
        poster_path="/poster.jpg",
        status="found",
    )
    db_session.add(metadata)

    db_session.commit()

    # Act: request movie details
    response = client.get("/movies/1")

    # Assert
    assert response.status_code == 200

    data = response.json()

    assert data["movie_id"] == 1
    assert data["title"] == "Inception"
    assert data["genres"] == "Action|Sci-Fi"

    # metadata-related fields
    assert "overview" in data
    assert "poster_url" in data