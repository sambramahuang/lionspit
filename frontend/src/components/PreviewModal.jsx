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
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Close
          </button>
        </div>

        {loading && <p className="spinner-text">Loading document preview...</p>}
        {error && <div className="error-banner">{error}</div>}
        {doc && <div className="preview-text">{doc.text}</div>}
      </div>
    </div>
  );
}
