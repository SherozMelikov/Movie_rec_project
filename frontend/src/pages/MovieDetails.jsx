import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  getMovie,
  getSimilar,
  trackView,
  isLiked,
  likeMovie,
  unlikeMovie,
  getMyRating,
  setRating,
} from "../api/api";

import MovieGrid from "../components/MovieGrid";
import "../styles/movieDetails.css";

/**
 * Survives React StrictMode remounts in development
 * because it lives outside the component instance.
 */
const trackedViews = new Set();

export default function MovieDetails() {
  const { movieId } = useParams();

  const [movie, setMovie] = useState(null);
  const [similar, setSimilar] = useState([]);
  const [liked, setLiked] = useState(false);
  const [rating, setMyRating] = useState(null);

  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;

    async function load() {
      setErr("");
      setLoading(true);

      try {
        // Prevent duplicate POST /events for the same movie id
        // during React StrictMode remounts in development
        if (movieId && !trackedViews.has(movieId)) {
          trackedViews.add(movieId);
          await trackView(movieId);
        }

        const [m, sim, likedRes, ratingRes] = await Promise.all([
          getMovie(movieId),
          getSimilar(movieId, 12),
          isLiked(movieId),
          getMyRating(movieId),
        ]);

        if (!alive) return;

        setMovie(m);
        setSimilar(Array.isArray(sim) ? sim : []);
        setLiked(!!likedRes?.liked);
        setMyRating(ratingRes?.score ?? null);
      } catch {
        if (!alive) return;
        setErr("Failed to load movie");
      } finally {
        if (!alive) return;
        setLoading(false);
      }
    }

    load();

    return () => {
      alive = false;
    };
  }, [movieId]);

  const genreList = useMemo(() => {
    if (!movie?.genres) return [];

    if (Array.isArray(movie.genres)) {
      return movie.genres.filter(Boolean);
    }

    return String(movie.genres)
      .split("|")
      .map((g) => g.trim())
      .filter(Boolean);
  }, [movie]);

  const genreText = genreList.join(" · ");

  async function onToggleLike() {
    try {
      if (liked) {
        await unlikeMovie(movieId);
        setLiked(false);
      } else {
        await likeMovie(movieId);
        setLiked(true);
      }
    } catch {
      // optional toast later
    }
  }

  async function onRate(score) {
    if (rating === score) return;
    try {
      const res = await setRating(movieId, score);
      setMyRating(res?.score ?? score);
    } catch {
      // optional toast later
    }
  }

  if (loading) {
    return (
      <div className="md-page">
        <div className="md-container">
          <div className="md-hero">
            <div className="md-posterWrap">
              <div className="mdSkPoster" />
            </div>

            <div className="md-meta">
              <div className="skLine skTitle" style={{ width: "60%" }} />
              <div className="skLine" style={{ width: "40%" }} />
              <div style={{ height: 8 }} />
              <div className="skLine" style={{ width: "85%" }} />
              <div className="skLine" style={{ width: "78%" }} />
              <div className="skLine" style={{ width: "70%" }} />
            </div>
          </div>

          <div className="md-section">
            <h2 className="md-sectionTitle">Similar movies</h2>
            <div style={{ marginTop: 10 }} />
          </div>
        </div>
      </div>
    );
  }

  if (err) {
    return (
      <div className="md-page">
        <div className="md-container md-error" style={{ color: "#ff6b6b" }}>
          {err}
        </div>
      </div>
    );
  }

  if (!movie) {
    return (
      <div className="md-page">
        <div className="md-container md-error">Not found</div>
      </div>
    );
  }

  return (
    <div className="md-page">
      <div className="md-container">
        <div className="md-hero">
          <div className="md-posterWrap">
            {movie.poster_url ? (
              <img className="md-poster" src={movie.poster_url} alt={movie.title} />
            ) : (
              <div className="md-posterPh" />
            )}
          </div>

          <div className="md-meta">
            <div className="md-titleRow">
              <h1 className="md-title">{movie.title}</h1>
            </div>

            <div className="md-sub">
              {movie.release_date ? (
                <span className="md-pill">📅 {movie.release_date}</span>
              ) : null}

              {genreText ? <span className="md-pill">🎭 {genreText}</span> : null}
            </div>

            <div className="md-actions">
              <button
                type="button"
                className="iconBtn"
                onClick={onToggleLike}
                title={liked ? "Unlike" : "Like"}
                aria-label={liked ? "Unlike movie" : "Like movie"}
              >
                <span className={liked ? "heart heartActive" : "heart"}>
                  {liked ? "♥" : "♡"}
                </span>
              </button>

              <div className="md-stars" aria-label="Movie rating">
                {[1, 2, 3, 4, 5].map((s) => (
                  <button
                    key={s}
                    type="button"
                    className={`starBtn ${rating >= s ? "starFilled" : ""}`}
                    onClick={() => onRate(s)}
                    title={`Rate ${s}`}
                    aria-label={`Rate ${s} star${s > 1 ? "s" : ""}`}
                  >
                    ★
                  </button>
                ))}
              </div>
            </div>

            <p className="md-overview">
              {movie.overview ? movie.overview : <span className="md-muted">No overview.</span>}
            </p>
          </div>
        </div>

        <div className="md-section">
          <h2 className="md-sectionTitle">Similar movies</h2>

          {similar.length === 0 ? (
            <p className="md-muted">No similar movies found.</p>
          ) : (
            <MovieGrid items={similar} />
          )}
        </div>
      </div>
    </div>
  );
}