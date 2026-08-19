import React, { useRef, useState } from "react";
import { api } from "../api.js";

export default function UploadPanel({ onIngested }) {
  const inputRef = useRef(null);
  const [staged, setStaged] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const addFiles = (fileList) => {
    const files = Array.from(fileList);
    setStaged((prev) => [...prev, ...files]);
    setResults(null);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  };

  const runIngest = async () => {
    if (staged.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.ingest(staged);
      setResults(res);
      setStaged([]);
      onIngested?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <div
        className={`dropzone ${dragOver ? "dragover" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <div className="dropzone-icon" />
        <p className="dropzone-title">Drop documents here, or click to browse</p>
        <p className="dropzone-sub">.txt, .docx, .pdf — any mix, any naming convention</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      {staged.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div className="section-label" style={{ margin: "0 0 8px" }}>
            Staged for ingest <span className="count">{staged.length}</span>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
            {staged.map((f, i) => (
              <li key={i}>{f.name}</li>
            ))}
          </ul>
          <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
            <button className="btn btn-ink" onClick={runIngest} disabled={busy}>
              {busy ? "Reading & tagging..." : `Ingest ${staged.length} file(s)`}
            </button>
            <button className="btn btn-ghost" onClick={() => setStaged([])} disabled={busy}>
              Clear
            </button>
          </div>
        </div>
      )}

      {error && <div className="error-banner" style={{ marginTop: 14 }}>{error}</div>}

      {results && (
        <div style={{ marginTop: 16 }}>
          <div className="section-label" style={{ margin: "0 0 8px" }}>
            Last ingest result <span className="count">{results.length}</span>
          </div>
          <table className="doc-table">
            <thead>
              <tr>
                <th>File</th>
                <th>Status</th>
                <th>Detected type</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={i} className={r.conflict_warnings?.length > 0 ? "matter-row-conflict" : ""}>
                  <td className="doc-filename">{r.filename}</td>
                  <td>
                    {r.status !== "ingested" ? (
                      <span className="badge" style={{ background: "var(--flag-red-bg)", color: "var(--flag-red)" }}>
                        error
                      </span>
                    ) : r.conflict_warnings?.length > 0 ? (
                      <span className="badge badge-conflict">conflict flagged</span>
                    ) : (
                      <span className="badge badge-approved">indexed</span>
                    )}
                  </td>
                  <td className="mono">{r.metadata?.document_type || "—"}</td>
                  <td style={{ fontSize: 12.5, color: "var(--text-muted)" }}>
                    {r.status !== "ingested" ? (
                      r.error
                    ) : r.conflict_warnings?.length > 0 ? (
                      <>
                        {r.metadata?.short_description}
                        <p className="reason-text" style={{ marginTop: 4 }}>
                          {r.conflict_warnings[0]} See the Matters tab to review.
                        </p>
                      </>
                    ) : (
                      r.metadata?.short_description
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
