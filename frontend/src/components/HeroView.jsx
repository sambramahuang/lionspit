import React from "react";

// The "Start Here" tab's entire content: just the hero introduction and a
// way into the fuller overview (What this tool does + the firm's best
// work), which now lives on its own page rather than below the fold here.
export default function HeroView({ onExplore }) {
  return (
    <div className="hero hero-standalone">
      <h1 className="hero-title">Welcome to Kitsu.</h1>
      <p className="hero-subtitle">
        Your firm's collective knowledge, organized and searchable — ready the moment you need it.
      </p>
      {onExplore && (
        <button className="btn btn-primary hero-cta" onClick={onExplore}>
          See what this tool does
        </button>
      )}
    </div>
  );
}
