import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getGenres, searchMovies, getMyOnboarding, saveOnboarding } from "../api/api";

export default function Onboarding() {
  const nav = useNavigate();

  const [genres, setGenres] = useState([]);
  const [favGenres, setFavGenres] = useState([]);

  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [picked, setPicked] = useState([]); // store movie objects [{movie_id,title,genres,...}]
  const pickedIds = useMemo(() => new Set(picked.map((m) => m.movie_id)), [picked]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  // If onboarding already exists, skip this page
  useEffect(() => {
    (async () => {
      try {
        const existing = await getMyOnboarding();
        if (existing) {
          nav("/recommendations", { replace: true });
          return;
        }
        const g = await getGenres();
        setGenres(g);
      } catch (e) {
        setErr("Failed to load onboarding data");
      } finally {
        setLoading(false);
      }
    })();
  }, [nav]);

  function toggleGenre(g) {
    setFavGenres((prev) =>
      prev.includes(g) ? prev.filter((x) => x !== g) : [...prev, g]
    );
  }

  function togglePick(movie) {
    setPicked((prev) => {
      const exists = prev.some((m) => m.movie_id === movie.movie_id);
      if (exists) return prev.filter((m) => m.movie_id !== movie.movie_id);
      return [...prev, movie];
    });
  }

  async function onSearch(e) {
    e.preventDefault();
    setErr("");
    try {
      const data = await searchMovies(q, 20);
      setResults(data);
    } catch (e2) {
      setErr("Search failed");
    }
  }

  async function onSubmit() {
    setErr("");

    // You can tune these thresholds
    if (favGenres.length < 1) {
      setErr("Pick at least 1 favorite genre");
      return;
    }
    if (picked.length < 5) {
      setErr("Pick at least 5 movies");
      return;
    }

    setSaving(true);
    try {
      await saveOnboarding({
        favorite_genres: favGenres,
        picked_movie_ids: picked.map((m) => m.movie_id),
      });
      nav("/recommendations");
    } catch (e3) {
      setErr(e3?.response?.data?.detail || "Failed to save onboarding");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p>Loading onboarding...</p>;

  return (
    <div style={{ display: "grid", gap: 16, maxWidth: 900 }}>
      <h2>Tell us what you like</h2>

      {err && <p style={{ color: "crimson", whiteSpace: "pre-wrap" }}>{err}</p>}

      {/* Genres */}
      <div>
        <h3 style={{ marginBottom: 8 }}>Pick your favorite genres</h3>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {genres.map((g) => {
            const active = favGenres.includes(g);
            return (
              <button
                key={g}
                type="button"
                onClick={() => toggleGenre(g)}
                style={{
                  padding: "6px 10px",
                  borderRadius: 999,
                  border: "1px solid #ccc",
                  background: active ? "#222" : "#fff",
                  color: active ? "#fff" : "#222",
                  cursor: "pointer",
                }}
              >
                {g}
              </button>
            );
          })}
        </div>
        <p style={{ color: "#666", marginTop: 8 }}>
          Selected: {favGenres.length}
        </p>
      </div>

      {/* Movie search */}
      <div>
        <h3 style={{ marginBottom: 8 }}>Pick movies you’ve enjoyed</h3>
        <form onSubmit={onSearch} style={{ display: "flex", gap: 8 }}>
          <input
            placeholder="Search titles..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ flex: 1 }}
          />
          <button type="submit" disabled={!q}>
            Search
          </button>
        </form>

        {!!results.length && (
          <div style={{ marginTop: 10 }}>
            <p style={{ color: "#666", margin: "6px 0" }}>Search results</p>
            <ul style={{ display: "grid", gap: 8, paddingLeft: 18 }}>
              {results.map((m) => {
                const active = pickedIds.has(m.movie_id);
                return (
                  <li key={m.movie_id} style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <button
                      type="button"
                      onClick={() => togglePick(m)}
                      style={{
                        padding: "4px 8px",
                        borderRadius: 6,
                        border: "1px solid #ccc",
                        background: active ? "#222" : "#fff",
                        color: active ? "#fff" : "#222",
                        cursor: "pointer",
                        minWidth: 72,
                      }}
                    >
                      {active ? "Picked" : "Pick"}
                    </button>

                    <div>
                      <div style={{ fontWeight: 600 }}>{m.title}</div>
                      {m.genres ? <div style={{ color: "#666" }}>{m.genres}</div> : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>

      {/* Picked summary */}
      <div>
        <h3 style={{ marginBottom: 8 }}>Your picks ({picked.length})</h3>
        {picked.length === 0 ? (
          <p style={{ color: "#666" }}>Pick at least 5 movies to continue.</p>
        ) : (
          <ul style={{ display: "grid", gap: 6, paddingLeft: 18 }}>
            {picked.map((m) => (
              <li key={m.movie_id} style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <button
                  type="button"
                  onClick={() => togglePick(m)}
                  style={{
                    padding: "4px 8px",
                    borderRadius: 6,
                    border: "1px solid #ccc",
                    background: "#fff",
                    cursor: "pointer",
                  }}
                >
                  Remove
                </button>
                <span>{m.title}</span>
              </li>
            ))}
          </ul>
        )}

        <button
          type="button"
          onClick={onSubmit}
          disabled={saving}
          style={{
            marginTop: 12,
            padding: "10px 14px",
            borderRadius: 8,
            border: "1px solid #ccc",
            background: "#222",
            color: "#fff",
            cursor: "pointer",
            width: 220,
          }}
        >
          {saving ? "Saving..." : "Finish & See Recommendations"}
        </button>
      </div>
    </div>
  );
}
