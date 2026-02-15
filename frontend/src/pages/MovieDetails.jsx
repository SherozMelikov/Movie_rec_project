import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getMovie, getSimilar } from "../api/api";

export default function MovieDetails() {
  const { movieId } = useParams();
  const [movie, setMovie] = useState(null);
  const [similar, setSimilar] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;

    async function loadMovie() {
      setErr("");
      setLoading(true);
      try {
        const m = await getMovie(movieId);
        const sim = await getSimilar(movieId, 12);

        if (!alive) return;
        setMovie(m);
        setSimilar(sim);
      } catch (e) {
        if (!alive) return;
        setErr("Failed to load movie");
      } finally {
        if (!alive) return;
        setLoading(false);
      }
    }

    loadMovie();
    return () => {
      alive = false;
    };
  }, [movieId]);

  if (loading) return <p>Loading...</p>;
  if (err) return <p style={{ color: "crimson" }}>{err}</p>;
  if (!movie) return <p>Not found</p>;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", gap: 16 }}>
        {movie.poster_url ? (
          <img
            src={movie.poster_url}
            alt={movie.title}
            style={{ width: 180, borderRadius: 8 }}
          />
        ) : (
          <div style={{ width: 180, height: 260, background: "#eee", borderRadius: 8 }} />
        )}

        <div>
          <h2 style={{ marginTop: 0 }}>{movie.title}</h2>
          {movie.release_date ? <p>Release: {movie.release_date}</p> : null}
          {movie.genres ? <p style={{ color: "#666" }}>{movie.genres}</p> : null}
          {movie.overview ? <p>{movie.overview}</p> : <p style={{ color: "#666" }}>No overview</p>}
        </div>
      </div>

      <div>
        <h3>Similar movies</h3>
        <ul style={{ display: "grid", gap: 6, paddingLeft: 18 }}>
          {similar.map((m) => (
            <li key={m.movie_id}>
              <Link to={`/movies/${m.movie_id}`}>{m.title}</Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
