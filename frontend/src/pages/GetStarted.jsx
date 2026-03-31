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
        <section className="gsHeroGrid">
          <div className="gsHeroLeft">
            <div className="gsEyebrow">Personalized movie discovery</div>

            <h1 className="gsTitle">
              Find movies
              <br />
              you’ll actually
              <br />
              want to watch.
            </h1>

            <p className="gsSubtitle">
              Discover films tailored to your taste. Pick a few favorites, explore
              similar titles, and get recommendations that feel personal from the start.
            </p>

            <div className="gsCtaButtons">
              <Link to="/register" className="gsPrimaryBtn">
                Get started <span className="gsArrow">→</span>
              </Link>

              <Link to="/login" className="gsGhostBtn">
                I already have an account
              </Link>
            </div>

            <div className="gsMiniProof">
              <span className="gsProofItem">Tailored picks</span>
              <span className="gsProofDot" />
              <span className="gsProofItem">Fast discovery</span>
              <span className="gsProofDot" />
              <span className="gsProofItem">Similar movie search</span>
            </div>
          </div>

          <div className="gsHeroRight">
            <div className="gsShowcaseCard">
              <div className="gsShowcaseTop">
                <div>
                  <div className="gsShowcaseLabel">For tonight</div>
                  <div className="gsShowcaseTitle">Your next watch</div>
                </div>
                <div className="gsShowcaseBadge">Made for you</div>
              </div>

              <div className="gsPosterGrid">
                <div className="gsPoster gsPoster1">Sci-Fi</div>
                <div className="gsPoster gsPoster2">Drama</div>
                <div className="gsPoster gsPoster3">Thriller</div>
                <div className="gsPoster gsPoster4">Adventure</div>
              </div>

              <div className="gsShowcaseBottom">
                <div className="gsTasteCard">
                  <div className="gsTasteTitle">Built around your taste</div>
                  <div className="gsTasteText">
                    Start with a few movies you like and let MovieRec shape the rest.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="gsBenefits">
          <div className="gsSectionHeading">
            <h2>Why people would use it</h2>
            <p>
              A smoother way to discover movies without endless scrolling.
            </p>
          </div>

          <div className="gsFeatureRow">
            <div className="gsFeatureCard">
              <div className="gsFeatureIcon">✨</div>
              <div className="gsFeatureTitle">Personal from the start</div>
              <div className="gsFeatureText">
                Pick a few movies and get recommendations that already feel relevant.
              </div>
            </div>

            <div className="gsFeatureCard">
              <div className="gsFeatureIcon">🎯</div>
              <div className="gsFeatureTitle">Better matches</div>
              <div className="gsFeatureText">
                Discover films based on both your interests and movie similarity.
              </div>
            </div>

            <div className="gsFeatureCard">
              <div className="gsFeatureIcon">🍿</div>
              <div className="gsFeatureTitle">Less searching, more watching</div>
              <div className="gsFeatureText">
                Spend less time browsing and more time finding something worth watching.
              </div>
            </div>
          </div>
        </section>

        <section className="gsBottomCta">
          <div className="gsBottomCtaCard">
            <div>
              <h3>Ready to discover your next favorite movie?</h3>
              <p>
                Create an account, choose a few favorites, and start exploring recommendations made just for you.
              </p>
            </div>

            <div className="gsBottomActions">
              <Link to="/register" className="gsPrimaryBtn">
                Create account <span className="gsArrow">→</span>
              </Link>
            </div>
          </div>

          <div className="gsFooterHint">
            Demo project • Backend API available at <span className="gsCode">/docs</span>
          </div>
        </section>
      </main>
    </div>
  );
}