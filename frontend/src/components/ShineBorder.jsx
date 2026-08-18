import React from "react";

// Native conic-gradient shine ring (no deps) -- place as the first child
// of a `position: relative; overflow: hidden;` container. Sweeps in the
// app's own brass palette rather than a generic multicolor gradient, so
// it reads as "partner sign-off" gilding, not a startup landing page.
export function ShineBorder({ borderWidth = 1.5, duration = 12 }) {
  return (
    <div
      className="shine-border"
      style={{ "--shine-border-width": `${borderWidth}px`, "--shine-duration": `${duration}s` }}
      aria-hidden="true"
    />
  );
}
