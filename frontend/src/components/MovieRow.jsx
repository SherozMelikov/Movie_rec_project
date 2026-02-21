import React from "react";
import MovieCard from "./MovieCard";
import MovieCardSkeleton from "./MovieCardSkeleton";
import "../styles/rows.css";

export default function MovieRow({
  title,
  subtitle,
  items = [],
  loading = false,
  skeletonCount = 10,
}) {
  if (!loading && !items.length) return null;

  return (
    <section className="row">
      <div className="rowHead">
        <h3 className="rowTitle">{title}</h3>
        {subtitle ? <div className="rowSub">{subtitle}</div> : null}
      </div>

      <div className="rowScroller">
        {loading
          ? Array.from({ length: skeletonCount }).map((_, i) => (
              <MovieCardSkeleton key={`sk-${i}`} variant="row" />
            ))
          : items.map((m) => <MovieCard key={m.movie_id ?? m.id} movie={m} variant="row" />)}
      </div>
    </section>
  );
}
