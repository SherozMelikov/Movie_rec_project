import React, { useState } from "react";
import { fetchRecs } from "../services/api";

export default function Recommendations() {
  const [userId, setUserId] = useState("");
  const [movies, setMovies] = useState([]);

  const fetchRecommendations = async () => {
    try {
      const data = await fetchRecs(userId);
      const recs = Object.entries(data).map(([movie_id, score]) => ({
        movie_id,
        title: movie_id, // change to movie title if available from backend
        score,
      }));
      setMovies(recs);
    } catch (err) {
      console.error("Error fetching recommendations:", err);
      setMovies([]);
    }
  };

  return (
    <div>
      <h2>Movie Recommendations</h2>

      <input
        type="number"
        placeholder="Enter user id"
        value={userId}
        onChange={(e) => setUserId(e.target.value)}
      />

      <button onClick={fetchRecommendations}>Get Recommendations</button>

      <ul>
        {movies.map((movie, index) => (
          <li key={index}>
            {movie.title} — Score: {movie.score.toFixed(2)}
          </li>
        ))}
      </ul>
    </div>
  );
}
