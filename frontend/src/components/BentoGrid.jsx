import React from "react";

const ICON_PROPS = {
  width: 22,
  height: 22,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export function BentoGrid({ children }) {
  return <div className="bento-grid">{children}</div>;
}

export function BentoCard({ icon, name, description, wide, tall, children }) {
  return (
    <div
      className={`bento-card ${wide ? "bento-card-wide" : ""} ${tall ? "bento-card-tall" : ""}`}
    >
      <div className="bento-card-glyph" aria-hidden="true">
        {icon}
      </div>
      <div className="bento-card-body">
        <p className="bento-card-name">{name}</p>
        <p className="bento-card-desc">{description}</p>
        {children}
      </div>
    </div>
  );
}

export function SearchGlyph() {
  return (
    <svg {...ICON_PROPS}>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

export function ClauseGlyph() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M7 3h8l4 4v14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
      <path d="M9 12h6M9 16h4" />
    </svg>
  );
}

export function WallGlyph() {
  return (
    <svg {...ICON_PROPS}>
      <rect x="4" y="10" width="7" height="5" />
      <rect x="11" y="10" width="7" height="5" />
      <rect x="4" y="5" width="7" height="5" />
      <rect x="11" y="5" width="7" height="5" />
      <path d="M4 15h14" />
    </svg>
  );
}

export function ReasonGlyph() {
  return (
    <svg {...ICON_PROPS}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 16v-4M12 8h.01" />
    </svg>
  );
}

export function LineageGlyph() {
  return (
    <svg {...ICON_PROPS}>
      <circle cx="6" cy="6" r="2.2" />
      <circle cx="6" cy="18" r="2.2" />
      <circle cx="18" cy="12" r="2.2" />
      <path d="M8 6.6 15.8 11M8 17.4 15.8 13" />
    </svg>
  );
}

export function CiteGlyph() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M8 7c-2.2 1-3.4 2.9-3.4 5.4S5.8 17 8 17" />
      <path d="M16 7c-2.2 1-3.4 2.9-3.4 5.4S13.8 17 16 17" />
    </svg>
  );
}
