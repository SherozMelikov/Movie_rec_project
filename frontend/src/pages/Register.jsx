import React, { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "../styles/auth.css";

import { signup, getMyOnboarding, normalizeApiError } from "../api/api";
import { useAuth } from "../context/AuthContext";

export default function Register() {
  const nav = useNavigate();
  const { login } = useAuth();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState(() => localStorage.getItem("prefill_email") || "");
  const [password, setPassword] = useState("");

  const [formError, setFormError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const canSubmit = useMemo(
    () => username.trim() && email.trim() && password.length >= 6,
    [username, email, password]
  );

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
      await signup(username.trim(), email.trim(), password);

      // auto-login like Netflix
      await login(username.trim(), password);

      localStorage.removeItem("prefill_email");

      const onboarding = await getMyOnboarding();
      nav(onboarding ? "/recommendations" : "/onboarding");
    } catch (e2) {
      const n = normalizeApiError(e2);
      setFormError(n.formError || "Signup failed");
      setFieldErrors(n.fieldErrors || {});
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h2>Create account</h2>

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
            placeholder="Email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              clearFieldError("email");
              setFormError("");
            }}
            aria-invalid={!!fieldErrors.email}
            style={fieldErrors.email ? { outline: "2px solid #e50914" } : undefined}
            type="email"
            required
          />
          {fieldErrors.email ? (
            <div className="auth-error" style={{ marginTop: -8, marginBottom: 10 }}>
              {fieldErrors.email}
            </div>
          ) : null}

          <input
            className="auth-input"
            type="password"
            placeholder="Password (min 6)"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              clearFieldError("password");
              setFormError("");
            }}
            aria-invalid={!!fieldErrors.password}
            style={fieldErrors.password ? { outline: "2px solid #e50914" } : undefined}
            required
            minLength={6}
          />
          {fieldErrors.password ? (
            <div className="auth-error" style={{ marginTop: -8, marginBottom: 10 }}>
              {fieldErrors.password}
            </div>
          ) : null}

          <button className="auth-button" disabled={!canSubmit || loading}>
            {loading ? "Creating..." : "Sign up"}
          </button>
        </form>

        <div className="auth-link">
          Already have an account? <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
