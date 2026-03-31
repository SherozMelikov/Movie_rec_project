import React, { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "../styles/auth.css";

import { useAuth } from "../context/AuthContext";
import { getMyOnboarding, normalizeApiError } from "../api/api";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const [formError, setFormError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const canSubmit = useMemo(() => username.trim() && password, [username, password]);

  function clearFieldError(name) {
    setFieldErrors((prev) => {
      if (!prev[name]) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    }); 
  }

  async function onSubmit(e) {
    e.preventDefault();
    setFormError("");
    setFieldErrors({});
    setLoading(true);

    try {
      await login(username.trim(), password);

      const onboarding = await getMyOnboarding();
      nav(onboarding ? "/recommendations" : "/onboarding");
    } catch (e2) {
      const n = normalizeApiError(e2);
      setFormError(n.formError || "Login failed");
      setFieldErrors(n.fieldErrors || {});
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="auth-logo">M</div>
          <div className="auth-name">MovieRec</div>
        </div>

        <h2>Sign In</h2>
        <p className="auth-subtitle">Welcome back. Sign in to continue.</p>

        {formError ? (
          <div className="auth-error auth-error-banner">
            {formError}
          </div>
        ) : null}

        <form onSubmit={onSubmit}>
          <div className="auth-field">
            <input
              className={`auth-input ${fieldErrors.username ? "is-invalid" : ""}`}
              placeholder="Username"
              value={username}
              onChange={(e) => {
                setUsername(e.target.value);
                clearFieldError("username");
                setFormError("");
              }}
              aria-invalid={!!fieldErrors.username}
              required
            />
            {fieldErrors.username ? (
              <div className="auth-error">{fieldErrors.username}</div>
            ) : null}
          </div>

          <div className="auth-field">
            <input
              className={`auth-input ${fieldErrors.password ? "is-invalid" : ""}`}
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                clearFieldError("password");
                setFormError("");
              }}
              aria-invalid={!!fieldErrors.password}
              required
            />
            {fieldErrors.password ? (
              <div className="auth-error">{fieldErrors.password}</div>
            ) : null}
          </div>

          <button className="auth-button" disabled={!canSubmit || loading}>
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <div className="auth-link">
          New here? <Link to="/register">Create account</Link>
        </div>
      </div>
    </div>
  );
}