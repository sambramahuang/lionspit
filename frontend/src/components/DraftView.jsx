import React, { useState } from "react";
import { api } from "../api.js";

/** Splits draft text on [[n]] and [[GAP: ...]] markers and renders the
 * citation markers as clickable brass badges, so a lawyer can jump
 * straight from a clause to the precedent it came from. */
function renderDraftText(text, onCiteClick) {
  const parts = [];
  const regex = /\[\[(GAP:[^\]]*|\d+)\]\]/g;
  let lastIndex = 0;
  let match;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(<span key={key++}>{text.slice(lastIndex, match.index)}</span>);
    }
    const token = match[1];
    if (token.startsWith("GAP:")) {
      parts.push(
        <span key={key++} className="gap-badge">gap: {token.slice(4).trim()}</span>
      );
    } else {
      parts.push(
        <button key={key++} className="cite-badge" onClick={() => onCiteClick(token)}>
          {token}
        </button>
      );
    }
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) parts.push(<span key={key++}>{text.slice(lastIndex)}</span>);
  return parts;
}

export default function DraftView({ query, selectedDocIds, onCiteClick }) {
  const [instructions, setInstructions] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState(null);

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.draft({ query, doc_ids: selectedDocIds, instructions: instructions || null });
      setDraft(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleCiteClick = (marker) => {
    const citation = draft?.citations.find((c) => c.marker === marker);
    if (citation) onCiteClick(citation.doc_id);
  };

  return (
    <div className="card" style={{ marginTop: 10 }}>
      <div className="section-label" style={{ margin: "0 0 10px" }}>Draft from selected precedents</div>
      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <input
          className="filter-input"
          style={{ flex: 1, width: "auto" }}
          placeholder="Optional extra drafting instructions"
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
        />
        <button
          className="btn btn-primary"
          onClick={generate}
          disabled={busy || selectedDocIds.length === 0}
        >
          {busy ? "Drafting..." : `Generate draft from ${selectedDocIds.length} source(s)`}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {!draft && !busy && (
        <div className="empty-state">
          Select one or more precedents above, then generate a draft. Every
          clause pulled from a source is footnoted back to it — nothing is
          invented outside the selected documents.
        </div>
      )}

      {draft && (
        <div className="draft-layout" style={{ marginTop: 14 }}>
          <div className="draft-page">{renderDraftText(draft.draft_text, handleCiteClick)}</div>
          <div className="sources-panel">
            <div className="section-label" style={{ margin: 0 }}>
              Citations <span className="count">{draft.citations.length}</span>
            </div>
            {draft.citations.map((c) => (
              <div key={c.marker} className="card" style={{ padding: "12px 14px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="cite-badge">{c.marker}</span>
                  <span className="mono" style={{ fontSize: 11 }}>{c.filename}</span>
                </div>
                <p className="source-excerpt">"...{c.excerpt}"</p>
              </div>
            ))}
            {draft.gaps.length > 0 && (
              <div className="card" style={{ padding: "12px 14px" }}>
                <div className="section-label" style={{ margin: "0 0 6px" }}>Gaps flagged, not invented</div>
                <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12.5 }}>
                  {draft.gaps.map((g, i) => <li key={i}>{g}</li>)}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
