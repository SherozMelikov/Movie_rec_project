import React from "react";
import { Link } from "react-router-dom";
import "../styles/movies.css";

export default function MovieCard({ movie }) {
  const id = movie.movie_id ?? movie.id;

  return (
    <Link to={`/movies/${id}`} className="movieCard">
      <div className="moviePosterWrap">
        {movie.poster_url ? (
          <img
            className="moviePoster"
            src={movie.poster_url}
            alt={movie.title}
            loading="lazy"
          />
        ) : (
          <div className="moviePosterFallback" />
        )}
      </div>

      <div className="movieMeta">
        <div className="movieTitle">{movie.title}</div>
        {movie.release_date ? <div className="movieSub">{movie.release_date}</div> : null}
        {movie.genres ? <div className="movieSub">{movie.genres}</div> : null}
      </div>
    </Link>
  );
}
