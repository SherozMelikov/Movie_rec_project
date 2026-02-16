import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "../styles/auth.css";

import { signup, getMyOnboarding } from "../api/api";
import { useAuth } from "../context/AuthContext";

function errorToText(e) {
  const detail = e?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((x) => x.msg).join(" | ");
  return "Signup failed";
}

export default function Register() {
  const nav = useNavigate();
  const { login } = useAuth();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState(() => localStorage.getItem("prefill_email") || "");
  const [password, setPassword] = useState("");

  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);

    try {
      await signup(username, email, password);

      // auto-login like Netflix
      await login(username, password);

      localStorage.removeItem("prefill_email");

      const onboarding = await getMyOnboarding();
      nav(onboarding ? "/recommendations" : "/onboarding/genres");
    } catch (e2) {
      setErr(errorToText(e2));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h2>Create account</h2>

        <form onSubmit={onSubmit}>
          <input
            className="auth-input"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />

          <input
            className="auth-input"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            required
          />

          <input
            className="auth-input"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
          />

          <button className="auth-button" disabled={loading}>
            {loading ? "Creating..." : "Sign up"}
          </button>
        </form>

        {err && <div className="auth-error">{err}</div>}

        <div className="auth-link">
          Already have an account? <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
