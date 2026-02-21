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
        <h2>Sign In</h2>

        {formError ? (
          <div className="auth-error" style={{ marginBottom: 12 }}>
            {formError}
          </div>
        ) : null}

        <form onSubmit={onSubmit}>
          <input
            className="auth-input"
            placeholder="Username"
            value={username}
            onChange={(e) => {
              setUsername(e.target.value);
              clearFieldError("username");
              setFormError("");
            }}
            aria-invalid={!!fieldErrors.username}
            style={fieldErrors.username ? { outline: "2px solid #e50914" } : undefined}
            required
          />
          {fieldErrors.username ? (
            <div className="auth-error" style={{ marginTop: -8, marginBottom: 10 }}>
              {fieldErrors.username}
            </div>
          ) : null}

          <input
            className="auth-input"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              clearFieldError("password");
              setFormError("");
            }}
            aria-invalid={!!fieldErrors.password}
            style={fieldErrors.password ? { outline: "2px solid #e50914" } : undefined}
            required
          />
          {fieldErrors.password ? (
            <div className="auth-error" style={{ marginTop: -8, marginBottom: 10 }}>
              {fieldErrors.password}
            </div>
          ) : null}

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
