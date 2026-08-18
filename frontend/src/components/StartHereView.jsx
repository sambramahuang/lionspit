import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";

const TOP_PER_GROUP = 3;
const TOP_FIRMWIDE = 5;

// Highest-trust documents first: partner-approved beats not, then whoever
// the firm actually reaches for most (usage_count) -- the same signal
// search.py's ranking weights use, applied here to curate rather than rank.
function byTrust(a, b) {
  const pa = a.metadata.partner_approved ? 1 : 0;
  const pb = b.metadata.partner_approved ? 1 : 0;
  if (pa !== pb) return pb - pa;
  return (b.usage_count || 0) - (a.usage_count || 0);
}

export default function StartHereView({ onPreview, onGoToSearch }) {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.listDocuments().then(setDocs).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, []);

  const byPracticeArea = useMemo(() => {
    const groups = new Map();
    for (const d of docs) {
      const key = d.metadata.practice_area || "Uncategorized";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(d);
    }
    return [...groups.entries()]
      .map(([area, list]) => ({
        area,
        count: list.length,
        matterTypes: [...new Set(list.map((d) => d.metadata.matter_type).filter(Boolean))],
        top: [...list].sort(byTrust).slice(0, TOP_PER_GROUP),
      }))
      .sort((a, b) => b.count - a.count);
  }, [docs]);

  const mostRelied = useMemo(
    () =>
      [...docs]
        .filter((d) => (d.usage_count || 0) > 0)
        .sort((a, b) => (b.usage_count || 0) - (a.usage_count || 0))
        .slice(0, TOP_FIRMWIDE),
    [docs]
  );

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Start here</h1>
        <p className="page-subtitle">
          New to the team, or just picking up something outside your usual practice area? This is
          the firm's collective best work, organized so you don't have to already know where to
          look.
        </p>
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <div className="section-label" style={{ margin: "0 0 10px" }}>What this tool does</div>
        <div className="start-here-explainer">
          <div>
            <b>Search in plain English</b>
            <p>No need to know legal terms of art — describe what you need and the system finds it.</p>
          </div>
          <div>
            <b>See why, not just what</b>
            <p>Every result explains why it ranked, why something was rejected, or why it's restricted.</p>
          </div>
          <div>
            <b>Find the exact clause</b>
            <p>Switch to clause search on the Search &amp; Draft tab to find one provision, not a whole document.</p>
          </div>
          <div>
            <b>Draft with citations</b>
            <p>Every generated clause traces back to its source — nothing is invented.</p>
          </div>
        </div>
        {onGoToSearch && (
          <button className="btn btn-primary" style={{ marginTop: 14 }} onClick={onGoToSearch}>
            Go to Search &amp; Draft
          </button>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}
      {loading && <p className="spinner-text">Loading...</p>}

      {!loading && docs.length === 0 && (
        <div className="empty-state">
          Nothing indexed yet — once documents are ingested, this page curates the firm's most
          trusted precedents by practice area automatically.
        </div>
      )}

      {!loading && mostRelied.length > 0 && (
        <>
          <div className="section-label">Most relied upon firm-wide</div>
          <div className="result-grid" style={{ marginBottom: 24 }}>
            {mostRelied.map((d) => (
              <StartHereCard key={d.doc_id} doc={d} onPreview={onPreview} />
            ))}
          </div>
        </>
      )}

      {!loading && byPracticeArea.length > 0 && (
        <>
          <div className="section-label">By practice area</div>
          {byPracticeArea.map(({ area, count, matterTypes, top }) => (
            <div className="card margin-card" key={area} style={{ marginBottom: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
                <p className="result-title" style={{ margin: 0 }}>{area}</p>
                <span className="count">{count} document{count === 1 ? "" : "s"}</span>
              </div>
              {matterTypes.length > 0 && (
                <p className="result-meta" style={{ marginTop: 4 }}>{matterTypes.join(" · ")}</p>
              )}
              <div className="start-here-recs">
                {top.map((d) => (
                  <div key={d.doc_id} className="start-here-rec">
                    <div style={{ minWidth: 0 }}>
                      <div className="doc-filename" style={{ fontSize: 13 }}>{d.filename}</div>
                      {d.metadata.short_description && (
                        <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "2px 0 0" }}>
                          {d.metadata.short_description}
                        </p>
                      )}
                    </div>
                    <div style={{ display: "flex", gap: 6, alignItems: "center", flexShrink: 0 }}>
                      {d.metadata.partner_approved && <span className="badge badge-approved">approved</span>}
                      <button
                        type="button"
                        className="btn btn-ghost preview-btn"
                        onClick={() => onPreview?.(d.doc_id)}
                      >
                        Preview
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </>
      )}
    </>
  );
}

function StartHereCard({ doc, onPreview }) {
  const m = doc.metadata || {};
  return (
    <div className="card margin-card tone-kept">
      <div className="result-head">
        <div>
          <p className="result-title">{doc.filename}</p>
          <div className="result-meta">
            {[m.practice_area, m.matter_type, m.jurisdiction].filter(Boolean).join(" · ") || "metadata not detected"}
          </div>
        </div>
        <div className="result-actions">
          <span className="score-chip">used {doc.usage_count}×</span>
          <button type="button" className="btn btn-ghost preview-btn" onClick={() => onPreview?.(doc.doc_id)}>
            Preview
          </button>
        </div>
      </div>
      {m.short_description && (
        <p style={{ fontSize: 12.5, color: "var(--text-muted)", margin: "8px 0 0" }}>{m.short_description}</p>
      )}
      <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
        {m.partner_approved && <span className="badge badge-approved">partner-approved</span>}
      </div>
    </div>
  );
}
