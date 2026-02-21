import React from "react";
import "../styles/movies.css";

export default function MovieCardSkeleton({ variant = "grid" }) {
  return (
    <div
      className={`movieCard movieCard--skeleton ${
        variant === "row" ? "movieCard--row" : "movieCard--grid"
      }`}
      aria-hidden="true"
    >
      <div className="moviePosterWrap">
        <div className="skPoster" />
        <div className="movieGradient" />
        <div className="movieMeta">
          <div className="skLine skTitle" />
          {variant !== "row" ? <div className="skLine skSub" /> : null}
        </div>
      </div>
    </div>
  );
}
