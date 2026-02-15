import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getRecommendations } from "../api/api";

export default function Recommendations() {
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setErr("");
    setLoading(true);
    try {
      const data = await getRecommendations(30);
      setItems(data);
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
      <ul style={{ display: "grid", gap: 8, paddingLeft: 18 }}>
        {items.map((m) => (
          <li key={m.movie_id}>
            <Link to={`/movies/${m.movie_id}`}>{m.title}</Link>
            {m.score != null ? <span style={{ marginLeft: 8, color: "#666" }}>score: {m.score}</span> : null}
            {m.reason ? <div style={{ color: "#777" }}>{m.reason}</div> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
