import React from "react";
import MovieCard from "./MovieCard";
import MovieCardSkeleton from "./MovieCardSkeleton";
import "../styles/movies.css";

export default function MovieGrid({ items = [], loading = false, skeletonCount = 24 }) {
  return (
    <div className="movieGrid">
      {loading
        ? Array.from({ length: skeletonCount }).map((_, i) => (
            <MovieCardSkeleton key={`sk-${i}`} variant="grid" />
          ))
        : items.map((m) => (
            <MovieCard key={m.movie_id ?? m.id} movie={m} variant="grid" />
          ))}
    </div>
  );
}
