import React, { useEffect, useMemo, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { browseMovies, getMyOnboarding, saveOnboarding } from "../api/api";
import "../styles/onboardingWizard.css";

const MOVIE_SHOW = 12;
const MOVIE_MIN = 5;
const MOVIE_MAX = 12;

// helper
function pickRandom(arr, n) {
  const copy = [...arr];
  copy.sort(() => Math.random() - 0.5);
  return copy.slice(0, n);
}

// normalize API responses that may return {results:[]}, {items:[]}, etc.
function normalizeArrayResponse(x) {
  if (Array.isArray(x)) return x;
  if (Array.isArray(x?.results)) return x.results;
  if (Array.isArray(x?.items)) return x.items;
  if (Array.isArray(x?.movies)) return x.movies;
  if (Array.isArray(x?.data)) return x.data;
  return [];
}

function getMovieId(m, idx) {
  // Prefer DB ID (stable). Fallbacks are for safety.
  return m?.movie_id ?? m?.id ?? m?.tmdb_id ?? m?.movieId ?? `${m?.title ?? "movie"}-${idx}`;
}

function getPosterUrl(m) {
  return m?.poster_url ?? m?.posterUrl ?? m?.poster ?? "";
}

export default function OnboardingWizard() {
  const nav = useNavigate();

  const [moviePool, setMoviePool] = useState([]);
  const [movies, setMovies] = useState([]);
  const [moviePickedIds, setMoviePickedIds] = useState(new Set());

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  // Load once
  useEffect(() => {
    (async () => {
      try {
        const existing = await getMyOnboarding();
        if (existing) {
          nav("/recommendations", { replace: true });
          return;
        }

        // IMPORTANT: keep limit <= backend max to avoid 422
        const poolRaw = await browseMovies({ limit: 48 });
        const arr = normalizeArrayResponse(poolRaw);

        setMoviePool(arr);

        const preferred = arr.filter((m) => !!getPosterUrl(m));
        const base = preferred.length ? preferred : arr;

        setMovies(pickRandom(base, MOVIE_SHOW));
      } catch (e) {
        setErr("Couldn’t load movies. Please try again.");
      } finally {
        setLoading(false);
      }
    })();
  }, [nav]);

  const pickedCount = moviePickedIds.size;

  const canFinish = useMemo(() => {
    if (movies.length === 0) return false;
    if (pickedCount < MOVIE_MIN) return false;
    if (pickedCount > MOVIE_MAX) return false;
    return true;
  }, [movies.length, pickedCount]);

  const helperText = useMemo(() => {
    if (pickedCount === 0) return `Choose a few movies you enjoy. You can change this later.`;
    if (pickedCount < MOVIE_MIN) return `Pick ${MOVIE_MIN - pickedCount} more to continue.`;
    if (pickedCount > MOVIE_MAX) return `Please keep it to ${MOVIE_MAX} or fewer.`;
    return `Nice — this will personalize your recommendations.`;
  }, [pickedCount]);

  const toggleMovie = useCallback((id) => {
    setErr("");
    setMoviePickedIds((prev) => {
      const next = new Set(prev);

      // unpick
      if (next.has(id)) {
        next.delete(id);
        return next;
      }

      // pick (respect max)
      if (next.size >= MOVIE_MAX) {
        // gentle, non-stressful message
        setErr(`You can pick up to ${MOVIE_MAX}. Unpick one to add another.`);
        return next;
      }

      next.add(id);
      return next;
    });
  }, []);

  const shuffleMovies = useCallback(() => {
    setErr("");
    const preferred = moviePool.filter((m) => !!getPosterUrl(m));
    const base = preferred.length ? preferred : moviePool;

    setMovies(pickRandom(base, MOVIE_SHOW));
    // Keep picks or reset? Netflix usually keeps picks.
    // I’ll keep picks to reduce frustration:
    // setMoviePickedIds(new Set());
  }, [moviePool]);

  const finish = useCallback(() => {
    setErr("");

    if (movies.length === 0) {
      setErr("No movies loaded yet. Tap Shuffle to try again.");
      return;
    }
    if (pickedCount < MOVIE_MIN) {
      setErr(`Pick ${MOVIE_MIN - pickedCount} more to continue.`);
      return;
    }
    if (pickedCount > MOVIE_MAX) {
      setErr(`Please pick ${MOVIE_MAX} or fewer.`);
      return;
    }

    (async () => {
      setSaving(true);
      try {
        await saveOnboarding({
          picked_movie_ids: Array.from(moviePickedIds),
        });
        nav("/recommendations");
      } catch (e) {
        setErr(e?.response?.data?.detail || "Couldn’t save your picks. Please try again.");
      } finally {
        setSaving(false);
      }
    })();
  }, [moviePickedIds, movies.length, nav, pickedCount]);

  if (loading) {
    return (
      <div className="onbW-page">
        <div className="onbW-card">
          <div className="onbW-top">
            <h2 className="onbW-title">Setting things up…</h2>
          </div>
          <p className="onbW-sub">Loading movies for you.</p>
          {/* (No progress bar here = less pressure) */}
        </div>
      </div>
    );
  }

  return (
    <div className="onbW-page">
      <div className="onbW-card">
        {/* Header */}
        <div className="onbW-header">
          <div className="onbW-top">
            <h2 className="onbW-title">Pick a few movies you like</h2>

            {/* Only show count once the user starts picking (less pressure) */}
            {pickedCount > 0 ? (
              <div className="onbW-step" style={{ fontWeight: 800 }}>
                {pickedCount}/{MOVIE_MAX}
              </div>
            ) : null}
          </div>
        </div>

        <p className="onbW-sub">{helperText}</p>

        {err ? <div className="onbW-error">{err}</div> : null}

        <div className="onbW-body">
          {movies.length === 0 ? (
            <div className="onbW-empty">
              <div className="onbW-emptyTitle">No movies to show</div>
              <div className="onbW-emptySub">
                Tap <b>Shuffle</b> to try again.
              </div>
              <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
                <button
                  type="button"
                  className="onbW-secondary"
                  onClick={shuffleMovies}
                  disabled={saving}
                >
                  Shuffle
                </button>
              </div>
              <div className="onbW-emptyMeta">
                pool={moviePool.length} • shown={movies.length}
              </div>
            </div>
          ) : (
            <>
              <div className="onbW-movieGrid">
                {movies.map((m, idx) => {
                  const id = getMovieId(m, idx);
                  const active = moviePickedIds.has(id);
                  const poster = getPosterUrl(m);

                  return (
                    <button
                      key={id}
                      type="button"
                      className={`onbW-miniCard ${active ? "onbW-miniCardActive" : ""}`}
                      onClick={() => toggleMovie(id)}
                      aria-pressed={active}
                      title={active ? "Selected (click to remove)" : "Click to select"}
                    >
                      {poster ? (
                        <img className="onbW-miniPoster" src={poster} alt={m.title} />
                      ) : (
                        <div className="onbW-miniPh" />
                      )}

                      <div className="onbW-miniGrad" />
                      <div className="onbW-miniHover" />

                      <div className="onbW-miniMeta">
                        <div className="onbW-miniTitle">{m.title}</div>
                      </div>

                      {active ? <div className="onbW-picked">✓ Selected</div> : null}
                    </button>
                  );
                })}
              </div>

              {/* Tools row: keep it minimal */}
              <div className="onbW-movieTools">
                <button
                  type="button"
                  className="onbW-secondary"
                  onClick={shuffleMovies}
                  disabled={saving}
                >
                  Shuffle
                </button>

                <button
                  type="button"
                  className="onbW-primary"
                  onClick={finish}
                  disabled={saving || !canFinish}
                >
                  {saving ? "Saving..." : "Continue"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}