import React, { useEffect, useState } from "react";
import { getRecommendations } from "../api/api";
import MovieGrid from "../components/MovieGrid";

export default function Recommendations() {
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setErr("");
    setLoading(true);
    try {
      const data = await getRecommendations(30);
      setItems(Array.isArray(data) ? data : []);
    } catch (e) {
      setErr(e?.response?.data?.detail || "Failed to load recommendations (login required)");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (loading) return <p>Loading...</p>;
  if (err) return <p style={{ color: "crimson" }}>{err}</p>;

  return (
    <div>
      <h2>Your Recommendations</h2>
      <MovieGrid items={items} />
    </div>
  );
}
