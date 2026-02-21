import React, { useEffect, useMemo, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { browseMovies, getGenres, getMyOnboarding, saveOnboarding } from "../api/api";
import "../styles/onboardingWizard.css";

const GENRE_SHOW = 8;
const GENRE_MIN = 3;
const GENRE_MAX = 5;

const MOVIE_SHOW = 6;
const MOVIE_MIN = 3;

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
  return m?.movie_id ?? m?.id ?? m?.tmdb_id ?? m?.movieId ?? `${m?.title ?? "movie"}-${idx}`;
}

function getPosterUrl(m) {
  return m?.poster_url ?? m?.posterUrl ?? m?.poster ?? "";
}

export default function OnboardingWizard() {
  const nav = useNavigate();

  const [step, setStep] = useState(1);

  const [allGenres, setAllGenres] = useState([]);
  const [shownGenres, setShownGenres] = useState([]);
  const [genrePicks, setGenrePicks] = useState([]);
  const [genreQuery, setGenreQuery] = useState("");

  const [moviePool, setMoviePool] = useState([]);
  const [movies, setMovies] = useState([]);
  const [moviePickedIds, setMoviePickedIds] = useState(new Set());

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const progressPct = step === 1 ? 50 : 100;

  // Load onboarding prerequisites once
  useEffect(() => {
    (async () => {
      try {
        const existing = await getMyOnboarding();
        if (existing) {
          nav("/recommendations", { replace: true });
          return;
        }

        // ---- Genres ----
        const g = await getGenres();
        const rawGenres = normalizeArrayResponse(g);

        const cleanedGenres = [...new Set(rawGenres.map(String))]
          .map((x) => x.trim())
          .filter((x) => x && x.toLowerCase() !== "(no genres listed)");

        setAllGenres(cleanedGenres);
        setShownGenres(pickRandom(cleanedGenres, GENRE_SHOW));

        // ---- Movies ----
        const poolRaw = await browseMovies({ limit: 120 });
        const arr = normalizeArrayResponse(poolRaw);

        setMoviePool(arr);

        const preferred = arr.filter((m) => !!getPosterUrl(m));
        const base = preferred.length ? preferred : arr;

        setMovies(pickRandom(base, MOVIE_SHOW));
      } catch (e) {
        setErr("Failed to load onboarding.");
      } finally {
        setLoading(false);
      }
    })();
  }, [nav]);

  const canGoNext = useMemo(() => {
    if (step === 1) return genrePicks.length >= GENRE_MIN;
    return moviePickedIds.size >= MOVIE_MIN && movies.length > 0;
  }, [step, genrePicks, moviePickedIds, movies]);

  const footText = useMemo(() => {
    if (step === 1) return `${genrePicks.length} selected (min ${GENRE_MIN}, max ${GENRE_MAX})`;
    return `${moviePickedIds.size} selected (min ${MOVIE_MIN})`;
  }, [step, genrePicks, moviePickedIds]);

  const toggleGenre = useCallback((g) => {
    setErr("");
    setGenrePicks((prev) => {
      const has = prev.includes(g);
      if (has) return prev.filter((x) => x !== g);
      if (prev.length >= GENRE_MAX) {
        setErr(`Max ${GENRE_MAX} genres. Unselect one to add another.`);
        return prev;
      }
      return [...prev, g];
    });
  }, []);

  const toggleMovie = useCallback((id) => {
    setErr("");
    setMoviePickedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const showMoreGenres = useCallback(() => {
    setErr("");
    const q = genreQuery.trim().toLowerCase();
    const filtered = q
      ? allGenres.filter((g) => g.toLowerCase().includes(q))
      : allGenres;
    setShownGenres(pickRandom(filtered.length ? filtered : allGenres, GENRE_SHOW));
  }, [allGenres, genreQuery]);

  const shuffleMovies = useCallback(() => {
    setErr("");
    const preferred = moviePool.filter((m) => !!getPosterUrl(m));
    const base = preferred.length ? preferred : moviePool;
    setMovies(pickRandom(base, MOVIE_SHOW));
    setMoviePickedIds(new Set());
  }, [moviePool]);

  const goBack = useCallback(() => {
    setErr("");
    if (step === 2) setStep(1);
  }, [step]);

  const goNext = useCallback(() => {
    setErr("");

    if (step === 1) {
      if (genrePicks.length < GENRE_MIN) {
        setErr(`Pick at least ${GENRE_MIN} genres to continue.`);
        return;
      }
      setStep(2);
      return;
    }

    // Step 2 validation
    if (movies.length === 0) {
      setErr("No movies loaded. Please click Shuffle/Retry.");
      return;
    }
    if (moviePickedIds.size < MOVIE_MIN) {
      setErr(`Pick at least ${MOVIE_MIN} movies to continue.`);
      return;
    }

    (async () => {
      setSaving(true);
      try {
        await saveOnboarding({
          favorite_genres: genrePicks,
          picked_movie_ids: Array.from(moviePickedIds),
        });
        nav("/recommendations");
      } catch (e) {
        setErr(e?.response?.data?.detail || "Failed to save onboarding.");
      } finally {
        setSaving(false);
      }
    })();
  }, [step, genrePicks, moviePickedIds, movies, nav]);

  if (loading) {
    return (
      <div className="onbW-page">
        <div className="onbW-card">
          <div className="onbW-top">
            <h2 className="onbW-title">Personalizing…</h2>
            <div className="onbW-step">Step 1/2</div>
          </div>
          <p className="onbW-sub">Loading onboarding…</p>
          <div className="onbW-progress">
            <div className="onbW-progressFill" style={{ width: "35%" }} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="onbW-page">
      <div className="onbW-card">
        {/* Header + stepper */}
        <div className="onbW-header">
          <div className="onbW-top">
            <h2 className="onbW-title">
              {step === 1 ? "Pick genres you like" : "Pick a few movies"}
            </h2>
            <div className="onbW-step">Step {step}/2</div>
          </div>

          <div className="onbW-stepper" aria-label="Onboarding steps">
            <div className="onbW-stepLabel">
              <span className={`onbW-dot ${step === 1 ? "onbW-dotActive" : ""}`} />
              Genres
            </div>
            <span className="onbW-arrow">→</span>
            <div className="onbW-stepLabel">
              <span className={`onbW-dot ${step === 2 ? "onbW-dotActive" : ""}`} />
              Movies
            </div>
          </div>
        </div>

        <p className="onbW-sub">
          {step === 1
            ? `Choose ${GENRE_MIN}+ genres (max ${GENRE_MAX}).`
            : `Pick ${MOVIE_MIN}+ movies to improve your first recommendations.`}
        </p>

        <div className="onbW-progress">
          <div className="onbW-progressFill" style={{ width: `${progressPct}%` }} />
        </div>

        {err ? <div className="onbW-error">{err}</div> : null}

        <div className="onbW-body">
          {step === 1 ? (
            <>
              <div className="onbW-inputRow">
                <input
                  className="onbW-input"
                  value={genreQuery}
                  onChange={(e) => setGenreQuery(e.target.value)}
                  placeholder="Search genres…"
                  onKeyDown={(e) => (e.key === "Enter" ? showMoreGenres() : null)}
                />
                <button type="button" className="onbW-secondary" onClick={showMoreGenres}>
                  More
                </button>
              </div>

              <div className="onbW-chips">
                {shownGenres.map((g) => {
                  const active = genrePicks.includes(g);
                  const disabled = !active && genrePicks.length >= GENRE_MAX;

                  return (
                    <button
                      key={g}
                      type="button"
                      className={`onbW-chip ${active ? "onbW-chipActive" : ""}`}
                      onClick={() => toggleGenre(g)}
                      disabled={disabled}
                      aria-pressed={active}
                      title={disabled ? `Max ${GENRE_MAX} genres` : ""}
                    >
                      {g}
                    </button>
                  );
                })}
              </div>
            </>
          ) : (
            <>
              {/* If movies are empty, show a friendly fallback instead of a blank page */}
              {movies.length === 0 ? (
                <div className="onbW-empty">
                  <div className="onbW-emptyTitle">No movies loaded</div>
                  <div className="onbW-emptySub">
                    Click <b>Shuffle</b> to retry loading movies.
                  </div>
                  <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
                    <button type="button" className="onbW-secondary" onClick={shuffleMovies} disabled={saving}>
                      Retry / Shuffle
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
                          title={active ? "Unpick" : "Pick"}
                        >
                          {poster ? (
                            <img className="onbW-miniPoster" src={poster} alt={m.title} />
                          ) : (
                            <div className="onbW-miniPh" />
                          )}

                          <div className="onbW-miniGrad" />
                          <div className="onbW-miniHover" />
                          <div className="onbW-miniCTA">{active ? "Picked" : "Pick"}</div>

                          <div className="onbW-miniMeta">
                            <div className="onbW-miniTitle">{m.title}</div>
                          </div>

                          {active ? <div className="onbW-picked">✓ Picked</div> : null}
                        </button>
                      );
                    })}
                  </div>

                  <div className="onbW-movieTools">
                    <div className="onbW-badge">
                      Selected: <b>{moviePickedIds.size}</b> / {MOVIE_MIN} min
                    </div>

                    <button type="button" className="onbW-secondary" onClick={shuffleMovies} disabled={saving}>
                      Shuffle
                    </button>
                  </div>
                </>
              )}
            </>
          )}
        </div>

        {/* Footer actions */}
        <div className="onbW-row">
          <button className="onbW-secondary" onClick={goBack} disabled={saving || step === 1}>
            Back
          </button>

          <div className="onbW-actions">
            <button className="onbW-primary" onClick={goNext} disabled={saving || !canGoNext}>
              {saving ? "Saving..." : step === 1 ? "Next →" : "Finish →"}
            </button>
          </div>
        </div>

        {/* show footnote only when user hasn't met the minimum */}
        {!canGoNext ? <div className="onbW-footNote">{footText}</div> : null}
      </div>
    </div>
  );
}