import React, { useEffect, useState, useCallback, useRef } from "react";
import { getRecommendationSections } from "../api/api";
import MovieRow from "../components/MovieRow";

export default function Recommendations() {
  const [sections, setSections] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const didLoadRef = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const data = await getRecommendationSections(12);
      setSections(Array.isArray(data) ? data : []);
    } catch (e) {
      console.log("refresh failed", e);
    }
  }, []);

  const loadInitial = useCallback(async () => {
    setErr("");
    setLoading(true);
    try {
      const data = await getRecommendationSections(12);
      setSections(Array.isArray(data) ? data : []);
    } catch (e) {
      setErr(e?.response?.data?.detail || "Failed to load recommendations (login required)");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (didLoadRef.current) return;
    didLoadRef.current = true;
    loadInitial();
  }, [loadInitial]);

  if (loading) {
    return (
      <div>
        <h2 style={{ marginBottom: 6 }}>Recommendations</h2>
        <MovieRow title="Just for you" subtitle="Loading…" loading={true} />
        <MovieRow title="Because you liked…" subtitle="Loading…" loading={true} />
        <MovieRow title="Trending" subtitle="Loading…" loading={true} />
      </div>
    );
  }

  if (err) return <p style={{ color: "crimson" }}>{err}</p>;

  return (
    <div>
      <h2 style={{ marginBottom: 6 }}>Recommendations</h2>

      {sections.map((s, idx) => (
        <MovieRow
          key={`${s.title}-${idx}`}
          title={s.title}
          subtitle={s.subtitle}
          items={s.items || []}
          onActionDone={refresh}
        />
      ))}
    </div>
  );
}