import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { browseMovies, getMyOnboarding, saveOnboarding } from "../api/api";
import OnboardingShell from "../components/OnboardingShell";

export default function OnboardingMovies() {
  const nav = useNavigate();

  const [movies, setMovies] = useState([]);
  const [picked, setPicked] = useState(() => {
    try { return JSON.parse(localStorage.getItem("onb_picked_movies") || "[]"); }
    catch { return []; }
  });
  const pickedIds = useMemo(() => new Set(picked.map((m) => m.movie_id)), [picked]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const favGenres = useMemo(() => {
    try { return JSON.parse(localStorage.getItem("onb_fav_genres") || "[]"); }
    catch { return []; }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const existing = await getMyOnboarding();
        if (existing) {
          nav("/recommendations", { replace: true });
          return;
        }
        if (!favGenres || favGenres.length === 0) {
          nav("/onboarding/genres", { replace: true });
          return;
        }
        const data = await browseMovies({ limit: 50 });
        setMovies(data);
      } catch {
        setErr("Failed to load movies");
      } finally {
        setLoading(false);
      }
    })();
  }, [nav, favGenres]);

  function togglePick(movie) {
    setPicked((prev) => {
      const exists = prev.some((m) => m.movie_id === movie.movie_id);
      const next = exists ? prev.filter((m) => m.movie_id !== movie.movie_id) : [...prev, movie];
      localStorage.setItem("onb_picked_movies", JSON.stringify(next));
      return next;
    });
  }

  async function onFinish() {
    setErr("");
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

      localStorage.removeItem("onb_fav_genres");
      localStorage.removeItem("onb_picked_movies");

      nav("/recommendations");
    } catch (e) {
      setErr(e?.response?.data?.detail || "Failed to save onboarding");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p>Loading onboarding...</p>;

  return (
    <OnboardingShell
      step={2}
      totalSteps={2}
      title="Pick movies you like"
      subtitle="Pick at least 5 so we can generate better recommendations."
      canBack={!saving}
      backTo="/onboarding/genres"
      canNext={!saving}
      onNext={onFinish}
      nextLabel="Finish"
      rightInfo={`Picked: ${picked.length} (min 5)`}
      busy={saving}
      error={err}
    >
      <ul style={{ display: "grid", gap: 8, paddingLeft: 18 }}>
        {movies.map((m) => {
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
    </OnboardingShell>
  );
}
