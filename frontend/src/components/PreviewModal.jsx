import React from "react";

// "Label: value" lines -- the convention every document in the corpus uses
// for its own header block (Matter/Client/Counterparty/From/To/Date/
// Subject/Practice area/... -- see case_documents/README.md), whether it's
// a printed-email PDF, a firm memo, or a plain-text file note. Matched
// generically by shape (short Title-Case label, colon, rest of line) so it
// doesn't need a hardcoded label list that drifts from the ingestion
// schema.
const KV_LINE_RE = /^[A-Z][A-Za-z][A-Za-z /]{0,28}:\s+\S.*$/;

// A short, mostly-uppercase line -- a firm name/letterhead or an ALL-CAPS
// section title ("FILE NOTE — PRECEDENT STATUS"), never a real sentence
// (those are lowercase-heavy even when they start with a capital).
function isShoutLine(line) {
  if (line.length > 90) return false;
  const letters = line.replace(/[^A-Za-z]/g, "");
  if (letters.length < 3) return false;
  const upper = line.replace(/[^A-Z]/g, "");
  return upper.length / letters.length > 0.8;
}

// Matches the same numbered-clause convention ingestion.py's clause
// splitter looks for ("1.", "Section 3:", "Clause 5.2", "4.1.2)") -- here
// only to bold the leading number/label so a clause-numbered document
// keeps a scannable rhythm, not to split the document itself.
const CLAUSE_LEAD_RE = /^((?:(?:Clause|Section|Article)\s+\d+(?:\.\d+)*[:.]?|\d+(?:\.\d+){0,3}[.)]))(\s+)/i;

function renderInline(line, key) {
  const m = line.match(CLAUSE_LEAD_RE);
  if (!m) return <React.Fragment key={key}>{line}</React.Fragment>;
  return (
    <React.Fragment key={key}>
      <strong>{m[1]}</strong>
      {m[2]}
      {line.slice(m[0].length)}
    </React.Fragment>
  );
}

// Groups the extracted text into visually distinct blocks -- a bordered
// key/value strip for a document's own header fields, a centered heading
// for a letterhead/section title, and justified paragraphs for the body
// (with numbered clause leads bolded) -- instead of one undifferentiated
// wall of pre-wrapped text. Pure presentation: never changes what text is
// shown, only how the existing line/paragraph structure from
// ingestion.extract_text is grouped.
function renderPreviewBlocks(text) {
  const blocks = text.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  return blocks.map((block, i) => {
    const lines = block.split("\n").map((l) => l.trim()).filter(Boolean);
    if (lines.length === 0) return null;

    if (lines.every(isShoutLine)) {
      return (
        <div className="preview-block preview-heading" key={i}>
          {lines.map((l, j) => (
            <div key={j}>{l}</div>
          ))}
        </div>
      );
    }

    if (lines.every((l) => KV_LINE_RE.test(l) || isShoutLine(l))) {
      return (
        <dl className="preview-block preview-kv" key={i}>
          {lines.map((l, j) => {
            const colon = l.indexOf(": ");
            if (colon === -1) {
              return <dd key={j} className="preview-kv-standalone">{l}</dd>;
            }
            return (
              <React.Fragment key={j}>
                <dt>{l.slice(0, colon)}</dt>
                <dd>{l.slice(colon + 2)}</dd>
              </React.Fragment>
            );
          })}
        </dl>
      );
    }

    return (
      <p className="preview-block preview-para" key={i}>
        {lines.map((l, j) => (
          <React.Fragment key={j}>
            {j > 0 && <br />}
            {renderInline(l, j)}
          </React.Fragment>
        ))}
      </p>
    );
  });
}

export default function PreviewModal({ open, doc, loading, error, onClose }) {
  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="preview-header">
          <div>
            <div className="preview-title">{doc ? doc.filename : "Document preview"}</div>
            {doc && (
              <div className="preview-meta">
                {[doc.metadata?.matter_type, doc.metadata?.jurisdiction, doc.metadata?.document_date, doc.metadata?.version]
                  .filter(Boolean)
                  .join(" · ") || "metadata not detected"}
              </div>
            )}
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close preview">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>

        {loading && <p className="spinner-text">Loading document preview...</p>}
        {error && <div className="error-banner">{error}</div>}
        {doc && <div className="preview-text">{renderPreviewBlocks(doc.text)}</div>}
      </div>
    </div>
  );
}
