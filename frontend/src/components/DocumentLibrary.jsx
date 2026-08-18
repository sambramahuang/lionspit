import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";

const FACET_FIELDS = [
  { key: "practice_area", label: "Practice area" },
  { key: "jurisdiction", label: "Jurisdiction" },
  { key: "matter_type", label: "Matter type" },
  { key: "document_type", label: "Document type" },
  { key: "client_type", label: "Client type" },
];

const EMPTY_FACETS = { practice_area: "", jurisdiction: "", matter_type: "", document_type: "", client_type: "" };

export default function DocumentLibrary({ refreshKey, onReset, onPreview }) {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [q, setQ] = useState("");
  const [facets, setFacets] = useState(EMPTY_FACETS);

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

  // Option lists are derived from whatever's actually in the corpus right
  // now, not a hardcoded taxonomy -- the metadata schema is auto-tagged
  // per document, so "what practice areas exist" is a question only the
  // data itself can answer.
  const facetOptions = useMemo(() => {
    const out = {};
    for (const { key } of FACET_FIELDS) {
      out[key] = [...new Set(docs.map((d) => d.metadata[key]).filter(Boolean))].sort((a, b) =>
        a.localeCompare(b)
      );
    }
    return out;
  }, [docs]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return docs.filter((d) => {
      for (const { key } of FACET_FIELDS) {
        if (facets[key] && d.metadata[key] !== facets[key]) return false;
      }
      if (!needle) return true;
      const haystack = [
        d.filename,
        d.metadata.short_description,
        d.metadata.client_name,
        d.metadata.counterparty_name,
      ]
        .filter(Boolean)
        .join(" \n ")
        .toLowerCase();
      return haystack.includes(needle);
    });
  }, [docs, facets, q]);

  const activeFilterCount = Object.values(facets).filter(Boolean).length + (q.trim() ? 1 : 0);
  const clearFilters = () => {
    setFacets(EMPTY_FACETS);
    setQ("");
  };

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div className="section-label" style={{ margin: 0 }}>
          Indexed documents{" "}
          <span className="count">
            {filtered.length}
            {activeFilterCount > 0 && docs.length !== filtered.length ? ` of ${docs.length}` : ""}
          </span>
        </div>
        <button className="btn btn-danger-ghost" onClick={handleReset}>
          Reset index
        </button>
      </div>

      {!loading && docs.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <input
            className="filter-input"
            style={{ width: "100%", marginBottom: 10 }}
            placeholder="Search by filename, client, or description..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <div className="filters-row">
            {FACET_FIELDS.map(({ key, label }) => (
              <select
                key={key}
                className="filter-input"
                value={facets[key]}
                onChange={(e) => setFacets((prev) => ({ ...prev, [key]: e.target.value }))}
              >
                <option value="">{label}: all</option>
                {facetOptions[key].map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            ))}
            {activeFilterCount > 0 && (
              <button className="btn btn-ghost" onClick={clearFilters}>
                Clear filters
              </button>
            )}
          </div>
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}
      {loading && <p className="spinner-text">Loading...</p>}

      {!loading && docs.length === 0 && (
        <div className="empty-state">
          Nothing indexed yet. Drop files above to seed the library, or run
          <span className="mono"> python seed_demo_data.py</span> from the backend.
        </div>
      )}

      {!loading && docs.length > 0 && filtered.length === 0 && (
        <div className="empty-state">No documents match these filters.</div>
      )}

      {!loading && filtered.length > 0 && (
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
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((d) => (
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
                  <td>
                    <button
                      type="button"
                      className="btn btn-ghost preview-btn"
                      onClick={() => onPreview?.(d.doc_id)}
                    >
                      Preview
                    </button>
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
