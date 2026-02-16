import React from "react";
import { useNavigate } from "react-router-dom";

export default function OnboardingShell({
  step,        // 1-based: 1,2,3...
  totalSteps,  // e.g. 2
  title,
  subtitle,
  canBack = true,
  canNext = true,
  backTo,
  nextTo,
  onNext,      // optional async
  nextLabel = "Next",
  backLabel = "Back",
  children,
  rightInfo,
  busy = false,
  error,
}) {
  const nav = useNavigate();
  const pct = Math.round((step / totalSteps) * 100);

  async function handleNext() {
    if (onNext) {
      await onNext();
      return;
    }
    if (nextTo) nav(nextTo);
  }

  function handleBack() {
    if (!canBack) return;
    if (backTo) nav(backTo);
    else nav(-1);
  }

  return (
    <div style={{ display: "grid", gap: 14, maxWidth: 900 }}>
      <div style={{ display: "grid", gap: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <h2 style={{ margin: 0 }}>{title}</h2>
          <span style={{ color: "#666" }}>
            Step {step} / {totalSteps}
          </span>
          <div style={{ marginLeft: "auto", color: "#666" }}>
            {rightInfo || null}
          </div>
        </div>

        {subtitle ? <div style={{ color: "#666" }}>{subtitle}</div> : null}

        {/* progress bar */}
        <div style={{ height: 8, background: "#eee", borderRadius: 999, overflow: "hidden" }}>
          <div style={{ width: `${pct}%`, height: "100%", background: "#222" }} />
        </div>

        {error ? <div style={{ color: "crimson", whiteSpace: "pre-wrap" }}>{error}</div> : null}
      </div>

      <div>{children}</div>

      {/* footer nav */}
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <button type="button" onClick={handleBack} disabled={!canBack || busy}>
          {backLabel}
        </button>

        <button type="button" onClick={handleNext} disabled={!canNext || busy}>
          {busy ? "Please wait..." : nextLabel}
        </button>
      </div>
    </div>
  );
}
