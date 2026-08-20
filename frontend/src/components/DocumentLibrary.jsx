import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";

const FACET_FIELDS = [
  { key: "practice_area", label: "Practice area" },
  { key: "jurisdiction", label: "Jurisdiction" },
  { key: "matter_type", label: "Matter type" },
  { key: "document_type", label: "Document type" },
  { key: "client_type", label: "Client type" },
  { key: "is_draft_or_model", label: "Document status" },
];

const EMPTY_FACETS = {
  practice_area: "",
  jurisdiction: "",
  matter_type: "",
  document_type: "",
  client_type: "",
  is_draft_or_model: "",
};

// is_draft_or_model's raw values are lowercase (ingestion.py's schema),
// unlike every other facet here which is free-text the LLM already
// extracts in natural casing -- map to a display label rather than
// showing "draft"/"model" literally in the filter dropdown.
const IS_DRAFT_OR_MODEL_LABELS = {
  draft: "Draft",
  model: "Model / template",
  executed: "Executed",
  unknown: "Unknown",
};
const facetOptionLabel = (key, value) =>
  key === "is_draft_or_model" ? IS_DRAFT_OR_MODEL_LABELS[value] || value : value;

export default function DocumentLibrary({ refreshKey, onChanged, onPreview, isPartner }) {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [q, setQ] = useState("");
  const [facets, setFacets] = useState(EMPTY_FACETS);
  const [deletingId, setDeletingId] = useState(null);
  const [approvingId, setApprovingId] = useState(null);

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
    onChanged?.();
  };

  const handleDelete = async (doc) => {
    if (!confirm(`Delete "${doc.filename}"? This can't be undone -- the document and its clauses are removed permanently.`)) return;
    setDeletingId(doc.doc_id);
    setError(null);
    try {
      await api.deleteDocument(doc.doc_id);
      onChanged?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setDeletingId(null);
    }
  };

  const handleApproval = async (doc) => {
    const approved = !doc.metadata.partner_approved;
    setApprovingId(doc.doc_id);
    setError(null);
    try {
      await api.setDocumentApproval(doc.doc_id, approved);
      onChanged?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setApprovingId(null);
    }
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
                  <option key={v} value={v}>{facetOptionLabel(key, v)}</option>
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
                <tr key={d.doc_id} className={d.access_restricted ? "doc-row-restricted" : ""}>
                  <td>
                    <div className="doc-filename">
                      {d.filename}
                      {d.access_restricted && (
                        <span className="badge badge-restricted" style={{ marginLeft: 6 }} title={d.restricted_reason}>
                          walled
                        </span>
                      )}
                    </div>
                    <div className="mono" style={{ color: "var(--text-muted)" }}>{d.doc_id}</div>
                  </td>
                  <td style={{ fontSize: 12.5 }}>
                    {d.metadata.matter_reference && (
                      <div className="mono" style={{ color: "var(--text-muted)", fontSize: 11 }}>
                        {d.metadata.matter_reference}
                      </div>
                    )}
                    {d.metadata.matter_type || "—"}
                    <div style={{ color: "var(--text-muted)" }}>{d.metadata.practice_area || ""}</div>
                  </td>
                  <td className="mono">{d.metadata.jurisdiction || "—"}</td>
                  <td className="mono">{d.metadata.document_date || "—"}</td>
                  <td className="mono">{d.metadata.version || "—"}</td>
                  <td>
                    {d.metadata.partner_approved ? (
                      <>
                        <span className="badge badge-approved">partner-approved</span>
                        {d.metadata.approved_by && (
                          <div className="approval-meta">
                            by {d.metadata.approved_by}
                            {d.metadata.approved_at && ` · ${new Date(d.metadata.approved_at).toLocaleDateString()}`}
                          </div>
                        )}
                      </>
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
                    <div style={{ display: "flex", gap: 6 }}>
                      <button
                        type="button"
                        className="btn btn-ghost preview-btn"
                        disabled={d.access_restricted}
                        title={d.access_restricted ? d.restricted_reason : undefined}
                        onClick={() => onPreview?.(d.doc_id)}
                      >
                        Preview
                      </button>
                      {/* Approve/delete stay hidden for a restricted row even for a
                          partner -- being walled off from a matter blocks acting on
                          its documents too, same rule the backend enforces (see
                          matters.is_blocked's docstring). */}
                      {isPartner && !d.access_restricted && (
                        <>
                          <button
                            type="button"
                            className={`btn ${d.metadata.partner_approved ? "btn-ghost" : "btn-primary"} preview-btn`}
                            disabled={approvingId === d.doc_id}
                            onClick={() => handleApproval(d)}
                          >
                            {approvingId === d.doc_id
                              ? "Updating…"
                              : d.metadata.partner_approved ? "Revoke approval" : "Approve"}
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger-ghost preview-btn"
                            disabled={deletingId === d.doc_id}
                            onClick={() => handleDelete(d)}
                          >
                            {deletingId === d.doc_id ? "Deleting…" : "Delete"}
                          </button>
                        </>
                      )}
                    </div>
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
