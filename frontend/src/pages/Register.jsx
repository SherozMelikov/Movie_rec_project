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
        <div className="auth-brand">
          <div className="auth-logo">M</div>
          <div className="auth-name">MovieRec</div>
        </div>

        <h2>Create account</h2>
        <p className="auth-subtitle">Join MovieRec and start discovering better movies.</p>

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
              className={`auth-input ${fieldErrors.email ? "is-invalid" : ""}`}
              placeholder="Email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                clearFieldError("email");
                setFormError("");
              }}
              aria-invalid={!!fieldErrors.email}
              type="email"
              required
            />
            {fieldErrors.email ? (
              <div className="auth-error">{fieldErrors.email}</div>
            ) : null}
          </div>

          <div className="auth-field">
            <input
              className={`auth-input ${fieldErrors.password ? "is-invalid" : ""}`}
              type="password"
              placeholder="Password (min 6)"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                clearFieldError("password");
                setFormError("");
              }}
              aria-invalid={!!fieldErrors.password}
              required
              minLength={6}
            />
            {fieldErrors.password ? (
              <div className="auth-error">{fieldErrors.password}</div>
            ) : null}
          </div>

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