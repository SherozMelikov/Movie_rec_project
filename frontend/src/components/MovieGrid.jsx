import React from "react";
import MovieCard from "./MovieCard";
import "../styles/movies.css";

export default function MovieGrid({ items }) {
  return (
    <div className="movieGrid">
      {items.map((m) => (
        <MovieCard key={m.movie_id ?? m.id} movie={m} />
      ))}
    </div>
  );
}
