import React from "react";

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
        {doc && <div className="preview-text">{doc.text}</div>}
      </div>
    </div>
  );
}
