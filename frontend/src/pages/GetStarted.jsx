import React from "react";
import { Link } from "react-router-dom";

import "../styles/getStarted.css";

export default function GetStarted() {
  return (
    <div className="gsPage">
      <div className="gsBgGlow" />

      <header className="gsTopbar">
        <Link to="/" className="gsBrand">
          <span className="gsBrandBadge">M</span>
          <span className="gsBrandName">MovieRec</span>

        </Link>

        <Link to="/login" className="gsSignInBtn">
          Sign In
        </Link>
      </header>

      <main className="gsWrap">
        <section className="gsHero">
          <h1 className="gsTitle">
            Your next movie,
            <br />
            recommended for you.
          </h1>

          <p className="gsSubtitle">
            A hybrid recommendation system using <b>ALS + HNSW</b>, with cold-start onboarding and fast similarity search.
          </p>

          <div className="gsFeatureRow">
            <div className="gsFeatureCard">
              <div className="gsFeatureTitle">Hybrid Rec Engine</div>
              <div className="gsFeatureText">Collaborative + content-based combined.</div>
            </div>

            <div className="gsFeatureCard">
              <div className="gsFeatureTitle">Cold-start Onboarding</div>
              <div className="gsFeatureText">First-time users get tailored picks fast.</div>
            </div>

            <div className="gsFeatureCard">
              <div className="gsFeatureTitle">Fast Similar Movies</div>
              <div className="gsFeatureText">HNSW index for quick similarity search.</div>
            </div>
          </div>

          <div className="gsCta">
            <div className="gsCtaText">
              Ready to start? Create an account and pick a few movies to personalize recommendations.
            </div>

            <div className="gsCtaButtons">
              <Link to="/register" className="gsPrimaryBtn">
                Get started <span className="gsArrow">→</span>
              </Link>
              <Link to="/login" className="gsGhostBtn">
                I already have an account
              </Link>
            </div>

            <div className="gsFooterHint">
              Demo project • Backend API available at <span className="gsCode">/docs</span>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
