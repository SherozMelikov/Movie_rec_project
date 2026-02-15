import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

function errorToText(e) {
  const detail = e?.response?.data?.detail;

  // FastAPI normal error: {detail: "message"}
  if (typeof detail === "string") return detail;

  // FastAPI validation error: {detail: [{loc,msg,type,input}, ...]}
  if (Array.isArray(detail)) {
    return detail
      .map((x) => {
        const where = Array.isArray(x.loc) ? x.loc.join(".") : String(x.loc || "");
        return where ? `${where}: ${x.msg}` : x.msg;
      })
      .join(" | ");
  }

  // Sometimes detail is a single object
  if (detail && typeof detail === "object") return detail.msg || "Login failed";

  return e?.message || "Login failed";
}

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await login(username, password);
      nav("/recommendations");
    } catch (e2) {
      setErr(errorToText(e2));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 420 }}>
      <h2>Login</h2>

      <form onSubmit={onSubmit} style={{ display: "grid", gap: 10 }}>
        <input
          placeholder="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />
        <input
          placeholder="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        <button disabled={loading} type="submit">
          {loading ? "Logging in..." : "Login"}
        </button>
      </form>

      {err && <p style={{ color: "crimson", whiteSpace: "pre-wrap" }}>{err}</p>}
    </div>
  );
}
