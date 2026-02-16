import React, { useEffect, useState } from "react";
import { browseMovies, searchMovies } from "../api/api";
import MovieGrid from "../components/MovieGrid";

export default function Home() {
  const [q, setQ] = useState("");
  const [movies, setMovies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function loadBrowse() {
    setErr("");
    setLoading(true);
    try {
      const data = await browseMovies({ limit: 20 });
      setMovies(data);
    } catch (e) {
      setErr("Failed to browse movies");
    } finally {
      setLoading(false);
    }
  }

  async function onSearch(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const data = await searchMovies(q, 20);
      setMovies(data);
    } catch (e) {
      setErr("Search failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadBrowse();
  }, []);

  return (
    <div>
      <h2>Browse / Search</h2>

      <form onSubmit={onSearch} style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          placeholder="Search title..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ flex: 1 }}
        />
        <button type="submit" disabled={!q || loading}>
          Search
        </button>
        <button type="button" onClick={loadBrowse} disabled={loading}>
          Reset
        </button>
      </form>

      {loading && <p>Loading...</p>}
      {err && <p style={{ color: "crimson" }}>{err}</p>}

      <MovieGrid items={movies} />
    </div>
  );
}
