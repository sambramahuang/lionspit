import React, { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api.js";
import { renderDraftHtml, downloadDraftTxt, downloadDraftDocx, downloadDraftPdf } from "../utils/draftExport.js";

/** Turns a query into a filesystem-safe stem for downloaded filenames --
 * falls back to "draft" for an empty/punctuation-only query. */
function slugify(text) {
  const slug = (text || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  return slug || "draft";
}

export default function DraftView({ query, selectedDocIds, onCiteClick }) {
  const [instructions, setInstructions] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState(null);
  const [exporting, setExporting] = useState(null); // null | "txt" | "docx" | "pdf"
  const [editKey, setEditKey] = useState(0);
  const draftRef = useRef(null);

  // The AI output as HTML, computed once per new draft -- memoized on
  // `draft` itself (not draft.draft_text derivatives) so unrelated
  // re-renders (typing in the instructions box, etc.) don't recompute
  // this string and reset the user's live in-place edits underneath them.
  const draftHtml = useMemo(() => (draft ? renderDraftHtml(draft.draft_text) : ""), [draft]);

  // Remounts the contentEditable node (via `key` below) from the fresh
  // draftHtml, either because a new draft just landed or because the
  // user hit "Reset edits" -- both cases want to discard whatever's
  // currently in the live-edited DOM.
  useEffect(() => {
    setEditKey((k) => k + 1);
  }, [draft]);

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

  // Citation badges are now plain DOM buttons (set via dangerouslySetInnerHTML,
  // not React-managed onClick handlers) -- one delegated listener on the
  // container catches clicks on any of them, including ones the user has
  // since moved around while editing.
  const handleDraftPageClick = (e) => {
    const btn = e.target.closest(".cite-badge");
    if (btn) handleCiteClick(btn.dataset.marker);
  };

  const resetEdits = () => setEditKey((k) => k + 1);

  const runExport = async (kind, fn) => {
    if (!draftRef.current || !draft) return;
    setExporting(kind);
    try {
      await fn(draftRef.current, draft, slugify(query));
    } catch (e) {
      setError(`Export failed: ${e.message}`);
    } finally {
      setExporting(null);
    }
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
          <div>
            <div className="draft-toolbar">
              <span className="draft-edit-hint">✎ Click into the draft below to edit it directly</span>
              <div className="draft-toolbar-actions">
                <button className="btn btn-ghost" onClick={resetEdits} disabled={!!exporting}>
                  Reset edits
                </button>
                <button className="btn btn-ghost" onClick={() => runExport("txt", downloadDraftTxt)} disabled={!!exporting}>
                  {exporting === "txt" ? "Exporting…" : "Download .txt"}
                </button>
                <button className="btn btn-ghost" onClick={() => runExport("docx", downloadDraftDocx)} disabled={!!exporting}>
                  {exporting === "docx" ? "Exporting…" : "Download .docx"}
                </button>
                <button className="btn btn-ghost" onClick={() => runExport("pdf", downloadDraftPdf)} disabled={!!exporting}>
                  {exporting === "pdf" ? "Exporting…" : "Download .pdf"}
                </button>
              </div>
            </div>
            <div
              key={editKey}
              ref={draftRef}
              className="draft-page"
              contentEditable
              suppressContentEditableWarning
              onClick={handleDraftPageClick}
              dangerouslySetInnerHTML={{ __html: draftHtml }}
            />
          </div>
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
