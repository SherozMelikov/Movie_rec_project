import React from "react";
import { Link } from "react-router-dom";
import "../styles/movies.css";

export default function MovieCard({ movie, variant = "grid" }) {
  const id = movie?.movie_id ?? movie?.id;
  const title = movie?.title ?? "Untitled";
  const poster = movie?.poster_url ?? null;

  return (
    <Link
      to={`/movies/${id}`}
      className={`movieCard ${variant === "row" ? "movieCard--row" : "movieCard--grid"}`}
      title={title}
    >
      <div className="moviePosterWrap">
        {poster ? (
          <img className="moviePoster" src={poster} alt={title} loading="lazy" />
        ) : (
          <div className="moviePosterFallback">
            <div className="fallbackBadge">No poster</div>
            <div className="fallbackTitle">{title}</div>
          </div>
        )}

        <div className="movieGradient" />

        <div className="movieMeta">
          <div className="movieTitle">{title}</div>

          {/* ✅ only show genres in GRID view (rows look cleaner without it) */}
          {variant !== "row" && movie?.genres ? (
            <div className="movieSub">{movie.genres}</div>
          ) : null}
        </div>
      </div>
    </Link>
  );
}
