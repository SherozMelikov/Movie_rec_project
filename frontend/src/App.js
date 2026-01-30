import { useState, useEffect } from "react";

function App() {
  const [movies, setMovies] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchRecommendations() {
      try {
        const res = await fetch("http://127.0.0.1:8000/recommendations/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: 1, top_k: 10 }),
        });
        const data = await res.json();
        setMovies(data.recommendations);
      } catch (err) {
        console.error("Error fetching recommendations:", err);
      } finally {
        setLoading(false);
      }
    }

    fetchRecommendations();
  }, []);

  if (loading) return <p>Loading recommendations...</p>;

  return (
    <div>
      <h1>Movie Recommendations</h1>
      <div style={{ display: "flex", flexWrap: "wrap" }}>
        {movies.map(movie => (
          <div key={movie.movie_id} style={{ margin: "10px", width: "200px" }}>
            <img
              src={movie.image_url}
              alt={movie.title}
              style={{ width: "100%", height: "300px", objectFit: "cover" }}
            />
            <h3>{movie.title}</h3>
            <p>{movie.genres}</p>
            <p>Score: {movie.score.toFixed(2)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;
