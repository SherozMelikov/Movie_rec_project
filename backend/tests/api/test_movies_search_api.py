##pytest tests/integration/test_movies_search_api.py -v

from app.db.models import Movie


def test_search_movie_by_title_returns_matching_results(client, db_session):
    # Arrange: add test movies to the test DB
    movie1 = Movie(movie_id=1, title="Inception", genres="Action|Sci-Fi")
    movie2 = Movie(movie_id=2, title="Interstellar", genres="Adventure|Sci-Fi")
    movie3 = Movie(movie_id=3, title="The Dark Knight", genres="Action|Crime")

    db_session.add_all([movie1, movie2, movie3])
    db_session.commit()

    # Act: search by title
    response = client.get("/movies/search", params={"q": "Inception"})

    # Assert: matching result is returned
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(movie["title"] == "Inception" for movie in data)