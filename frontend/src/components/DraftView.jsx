import React, { useState } from "react";
import { api } from "../api.js";

/** The model writes plain-text drafts but reaches for **bold** naturally
 * for headings/defined terms -- rendered literally as asterisks otherwise,
 * which reads as broken in what's meant to be the polished, trustworthy
 * output. Splits a plain-text run on **bold** spans into text/<strong>. */
function renderInlineMarkdown(text, keyPrefix) {
  const boldRegex = /\*\*(.+?)\*\*/g;
  const nodes = [];
  let lastIndex = 0;
  let match;
  let i = 0;

  while ((match = boldRegex.exec(text)) !== null) {
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));
    nodes.push(<strong key={`${keyPrefix}-b${i++}`}>{match[1]}</strong>);
    lastIndex = boldRegex.lastIndex;
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
}

/** Splits draft text on [[n]]/[[GAP: ...]]/[[UNCITED]] markers and
 * standalone "---" section dividers (the model sometimes writes one
 * before a trailing "Drafting notes" section), rendering markers as
 * clickable navy badges (citations), red badges (gaps, and clauses the
 * backend caught with neither a citation nor a gap marker -- see
 * drafting.py's _flag_uncited_clauses) and dividers as a real rule
 * instead of three literal dashes. Plain-text runs in between also get
 * markdown bold spans resolved (see above). */
function renderDraftText(text, onCiteClick) {
  const parts = [];
  const regex = /\[\[(GAP:[^\]]*|UNCITED|\d+)\]\]|^[ \t]*-{3,}[ \t]*$/gm;
  let lastIndex = 0;
  let match;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      const segment = text.slice(lastIndex, match.index);
      parts.push(<span key={key}>{renderInlineMarkdown(segment, `s${key}`)}</span>);
      key++;
    }
    const token = match[1];
    if (token === undefined) {
      parts.push(<hr key={key++} className="draft-divider" />);
    } else if (token === "UNCITED") {
      parts.push(
        <span key={key++} className="uncited-badge" title="Not cited to any source -- review before use">
          ⚠ uncited
        </span>
      );
    } else if (token.startsWith("GAP:")) {
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
  if (lastIndex < text.length) {
    const segment = text.slice(lastIndex);
    parts.push(<span key={key}>{renderInlineMarkdown(segment, `s${key}`)}</span>);
    key++;
  }
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
    <div className="card" style={{ marginTop: 30 }}>
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
            {draft.flagged_uncited?.length > 0 && (
              <div className="card" style={{ padding: "12px 14px" }}>
                <div className="section-label" style={{ margin: "0 0 6px" }}>
                  ⚠ Uncited clauses <span className="count">{draft.flagged_uncited.length}</span>
                </div>
                <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 8px" }}>
                  Written without a source citation or a flagged gap -- a drafting-prompt slip, not
                  a verified precedent. Review before relying on these.
                </p>
                <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12.5 }}>
                  {draft.flagged_uncited.map((c, i) => <li key={i}>{c}</li>)}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
