import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function DocumentLibrary({ refreshKey, onReset }) {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listDocuments();
      setDocs(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [refreshKey]);

  const handleReset = async () => {
    if (!confirm("Clear the entire index? This removes every ingested document.")) return;
    await api.resetDocuments();
    onReset?.();
  };

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div className="section-label" style={{ margin: 0 }}>
          Indexed documents <span className="count">{docs.length}</span>
        </div>
        <button className="btn btn-danger-ghost" onClick={handleReset}>
          Reset index
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {loading && <p className="spinner-text">Loading...</p>}

      {!loading && docs.length === 0 && (
        <div className="empty-state">
          Nothing indexed yet. Drop files above to seed the library, or run
          <span className="mono"> python seed_demo_data.py</span> from the backend.
        </div>
      )}

      {!loading && docs.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table className="doc-table">
            <thead>
              <tr>
                <th>File</th>
                <th>Matter / practice</th>
                <th>Jurisdiction</th>
                <th>Date</th>
                <th>Version</th>
                <th>Status</th>
                <th>Confidentiality</th>
                <th>Used</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.doc_id}>
                  <td>
                    <div className="doc-filename">{d.filename}</div>
                    <div className="mono" style={{ color: "var(--text-muted)" }}>{d.doc_id}</div>
                  </td>
                  <td style={{ fontSize: 12.5 }}>
                    {d.metadata.matter_type || "—"}
                    <div style={{ color: "var(--text-muted)" }}>{d.metadata.practice_area || ""}</div>
                  </td>
                  <td className="mono">{d.metadata.jurisdiction || "—"}</td>
                  <td className="mono">{d.metadata.document_date || "—"}</td>
                  <td className="mono">{d.metadata.version || "—"}</td>
                  <td>
                    {d.metadata.partner_approved ? (
                      <span className="badge badge-approved">partner-approved</span>
                    ) : (
                      <span className="badge badge-unapproved">unapproved</span>
                    )}
                  </td>
                  <td>
                    {d.metadata.confidentiality === "restricted" ? (
                      <span className="badge badge-restricted">restricted</span>
                    ) : (
                      <span className="mono" style={{ color: "var(--text-muted)" }}>{d.metadata.confidentiality}</span>
                    )}
                  </td>
                  <td className="mono">{d.usage_count}×</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
