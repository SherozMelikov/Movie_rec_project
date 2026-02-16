import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

export default function GetStarted() {
  const nav = useNavigate();
  const [email, setEmail] = useState("");

  function onGetStarted(e) {
    e.preventDefault();
    localStorage.setItem("prefill_email", email);
    nav("/register");
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        color: "#fff",
        background:
          "radial-gradient(1200px 500px at 20% 0%, rgba(229,9,20,.35), transparent 60%)," +
          "linear-gradient(120deg, #0b0b0b, #141414 55%, #0b0b0b)",
      }}
    >
      {/* Top bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          padding: "18px 24px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              background: "#e50914",
              display: "grid",
              placeItems: "center",
              fontWeight: 900,
            }}
          >
            M
          </div>
          <div style={{ fontWeight: 900, letterSpacing: 1, fontSize: 20 }}>
            MOVIEFLIX
          </div>
        </div>

        <div style={{ marginLeft: "auto" }}>
          <Link
            to="/login"
            style={{
              background: "#e50914",
              color: "#fff",
              padding: "10px 14px",
              borderRadius: 8,
              textDecoration: "none",
              fontWeight: 800,
            }}
          >
            Sign In
          </Link>
        </div>
      </div>

      {/* Hero */}
      <div
        style={{
          maxWidth: 980,
          margin: "0 auto",
          padding: "80px 24px 40px",
          display: "grid",
          gap: 18,
        }}
      >
        <h1 style={{ fontSize: 50, margin: 0, lineHeight: 1.08 }}>
          Your next movie,
          <br />
          recommended for you.
        </h1>

        <p style={{ fontSize: 18, color: "#cfcfcf", margin: 0, maxWidth: 760 }}>
          A hybrid recommendation system using <b>ALS</b> + <b>HNSW</b>, with cold-start
          onboarding and fast similarity search.
        </p>

        {/* Features */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
            gap: 12,
            marginTop: 10,
          }}
        >
          {[
            { title: "Hybrid Rec Engine", desc: "Collaborative + content-based combined." },
            { title: "Cold-start Onboarding", desc: "First-time users get tailored picks fast." },
            { title: "Fast Similar Movies", desc: "HNSW index for quick similarity search." },
          ].map((f) => (
            <div
              key={f.title}
              style={{
                background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.10)",
                borderRadius: 14,
                padding: 14,
              }}
            >
              <div style={{ fontWeight: 800 }}>{f.title}</div>
              <div style={{ color: "#cfcfcf", fontSize: 13, marginTop: 6 }}>{f.desc}</div>
            </div>
          ))}
        </div>

        {/* Get started form */}
        <form
          onSubmit={onGetStarted}
          style={{
            display: "flex",
            gap: 10,
            marginTop: 18,
            maxWidth: 720,
          }}
        >
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email address"
            type="email"
            required
            style={{
              flex: 1,
              padding: "14px 12px",
              borderRadius: 10,
              border: "1px solid rgba(255,255,255,0.16)",
              background: "rgba(0,0,0,0.35)",
              color: "#fff",
              fontSize: 15,
            }}
          />

          <button
            type="submit"
            style={{
              padding: "14px 16px",
              borderRadius: 10,
              border: "none",
              background: "#e50914",
              color: "#fff",
              fontWeight: 900,
              fontSize: 15,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            Get Started →
          </button>
        </form>

        <div style={{ color: "#9a9a9a", fontSize: 13 }}>
          Already have an account?{" "}
          <Link to="/login" style={{ color: "#e50914", textDecoration: "none" }}>
            Sign in
          </Link>
        </div>

        {/* Footer (optional) */}
        <div style={{ marginTop: 50, color: "#777", fontSize: 12 }}>
          Demo project • Backend API available at <span style={{ color: "#aaa" }}>/docs</span>
        </div>
      </div>
    </div>
  );
}
