import React from "react";

export default function ResultCard({ item, tone, reason, selectable, selected, onToggle, sourceRef, highlighted }) {
  const m = item.metadata || {};
  return (
    <div
      ref={sourceRef}
      className={`card margin-card tone-${tone} ${highlighted ? "pulse source-item" : "source-item"}`}
    >
      <div className="result-head">
        <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
          {selectable && (
            <input
              type="checkbox"
              checked={!!selected}
              onChange={() => onToggle?.(item.doc_id)}
              style={{ marginTop: 4 }}
            />
          )}
          <div>
            <p className="result-title">{item.filename}</p>
            <div className="result-meta">
              {[m.matter_type, m.jurisdiction, m.document_date, m.version && `v${m.version}`]
                .filter(Boolean)
                .join(" · ") || "metadata not detected"}
            </div>
          </div>
        </div>
        {typeof item.score === "number" && (
          <span className="score-chip">score {item.score.toFixed(2)}</span>
        )}
      </div>

      {m.short_description && (
        <p style={{ fontSize: 12.5, color: "var(--text-muted)", margin: "8px 0 0" }}>
          {m.short_description}
        </p>
      )}

      <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
        {m.partner_approved ? (
          <span className="badge badge-approved">partner-approved</span>
        ) : (
          <span className="badge badge-unapproved">unapproved</span>
        )}
        {m.confidentiality === "restricted" && <span className="badge badge-restricted">restricted</span>}
      </div>

      {item.score_breakdown && (
        <div className="breakdown-row">
          {Object.entries(item.score_breakdown).map(([k, v]) => (
            <span key={k}>{k.replace(/_/g, " ")}: {Number(v).toFixed(2)}</span>
          ))}
        </div>
      )}

      {reason && (
        <p className={tone === "restricted" ? "restricted-text" : "reason-text"}>{reason}</p>
      )}
    </div>
  );
}
