import React, { useEffect, useMemo, useRef, useState } from "react";
import { browseMovies, searchMovies } from "../api/api";
import MovieGrid from "../components/MovieGrid";
import "../styles/home.css";

function formatGenres(genres) {
  if (!genres) return [];
  return String(genres)
    .split("|")
    .map((g) => g.trim())
    .filter(Boolean)
    .slice(0, 4);
}

export default function Home() {
  const [q, setQ] = useState("");
  const [movies, setMovies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const didLoadRef = useRef(false);

  async function loadBrowse() {
    setErr("");
    setLoading(true);
    try {
      const data = await browseMovies({ limit: 24 });
      setMovies(Array.isArray(data) ? data : []);
    } catch {
      setErr("Failed to browse movies");
    } finally {
      setLoading(false);
    }
  }

  async function onSearch(e) {
    e.preventDefault();
    const query = q.trim();
    if (!query) return;

    setErr("");
    setLoading(true);
    try {
      const data = await searchMovies(query, 24);
      setMovies(Array.isArray(data) ? data : []);
    } catch {
      setErr("Search failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (didLoadRef.current) return;
    didLoadRef.current = true;
    loadBrowse();
  }, []);

  const featured = useMemo(() => {
    if (!movies?.length) return null;
    const withPoster = movies.filter((m) => !!m.poster_url);
    const pool = withPoster.length ? withPoster : movies;
    return pool[Math.floor(Math.random() * pool.length)];
  }, [movies]);

  const featuredGenres = formatGenres(featured?.genres);

  return (
    <div className="homePage">
      <div className="homeContainer">
        {featured ? (
          <div className="homeHero">
            <div
              className="homeHeroBg"
              style={{
                backgroundImage: featured.poster_url ? `url(${featured.poster_url})` : "none",
              }}
            />
            <div className="homeHeroOverlay" />

            <div className="homeHeroContent">
              <div className="homeHeroBadge">Featured</div>

              <h1 className="homeHeroTitle">{featured.title}</h1>

              <div className="homeHeroMeta">
                {featured.release_date ? <span className="pill">📅 {featured.release_date}</span> : null}
                {featuredGenres.length ? <span className="pill">🎭 {featuredGenres.join(" • ")}</span> : null}
              </div>

              <p className="homeHeroText">
                {featured.overview
                  ? featured.overview
                  : "Browse movies and build your taste profile. Like and rate to improve recommendations."}
              </p>

              <div className="homeHeroActions">
                <button
                  className="btnPrimary"
                  type="button"
                  onClick={() => (window.location.href = `/movies/${featured.movie_id ?? featured.id}`)}
                >
                  More Info
                </button>

                <button className="btnGhost" type="button" onClick={loadBrowse} disabled={loading}>
                  Refresh
                </button>
              </div>
            </div>
          </div>
        ) : null}

        <div className="homeHeader">
          <div>
            <h2 className="homeTitle">Browse</h2>
            <p className="homeSub">Search by title, then open a movie to like/rate it.</p>
          </div>

          <form onSubmit={onSearch} className="homeSearch">
            <input
              className="homeInput"
              placeholder="Search title…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
            <button className="btnPrimary" type="submit" disabled={!q.trim() || loading}>
              Search
            </button>
            <button className="btnGhost" type="button" onClick={loadBrowse} disabled={loading}>
              Reset
            </button>
          </form>
        </div>

        {err ? <div className="homeError">{err}</div> : null}

        <MovieGrid items={movies} loading={loading && movies.length === 0} skeletonCount={24} />
      </div>
    </div>
  );
}