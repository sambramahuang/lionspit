import React from "react";

export default function ClauseResultCard({ item, selectable, selected, onToggle, onPreview }) {
  const m = item.metadata || {};
  return (
    <div className="card margin-card tone-kept">
      <div className="result-head">
        <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
          <input
            type="checkbox"
            checked={!!selected}
            onChange={(event) => {
              event.stopPropagation();
              onToggle?.(item.doc_id);
            }}
            style={{ marginTop: 4, visibility: selectable ? "visible" : "hidden" }}
            tabIndex={selectable ? 0 : -1}
          />
          <div>
            <p className="result-title">{item.label || `Clause ${item.clause_index + 1}`}</p>
            <div className="result-meta">
              from <span className="mono">{item.filename}</span>
              {[m.matter_type, m.jurisdiction].filter(Boolean).length > 0 &&
                " · " + [m.matter_type, m.jurisdiction].filter(Boolean).join(" · ")}
            </div>
          </div>
        </div>

        <div className="result-actions">
          <span className="score-chip">match {item.similarity.toFixed(2)}</span>
          <button
            type="button"
            className="btn btn-ghost preview-btn"
            onClick={(event) => {
              event.stopPropagation();
              onPreview?.(item.doc_id);
            }}
          >
            View source
          </button>
        </div>
      </div>

      <p className="clause-excerpt">{item.text}</p>

      <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
        {m.partner_approved ? (
          <span className="badge badge-approved">partner-approved</span>
        ) : (
          <span className="badge badge-unapproved">unapproved</span>
        )}
        {m.confidentiality === "restricted" && <span className="badge badge-restricted">restricted</span>}
      </div>
    </div>
  );
}
