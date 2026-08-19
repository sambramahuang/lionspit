import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import {
  BentoCard,
  BentoGrid,
  CiteGlyph,
  ClauseGlyph,
  LineageGlyph,
  ReasonGlyph,
  SearchGlyph,
  WallGlyph,
} from "./BentoGrid.jsx";

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

export default function OverviewView({ onPreview, onGoToLibrary, onGoToSearch }) {
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
          Learn what Kitsu can do for your work, then explore the firm's best precedents below.
        </p>
      </div>

      <div className="start-here-bento">
        <BentoGrid>
        <BentoCard
          tall
          icon={<SearchGlyph />}
          name="Search in plain English"
          description='No need to know legal terms of art — describe what you need ("cap on founder liability if they breach the agreement") and the system finds it, ranked by similarity, recency, firm usage, partner approval, and jurisdiction match.'
        />
        <BentoCard
          icon={<ClauseGlyph />}
          name="Find the exact clause"
          description="Switch to clause search to find one provision — an indemnity cap, a notice period — instead of a whole document you'd have to read through."
        />
        <BentoCard
          icon={<WallGlyph />}
          name="Ethical walls, enforced"
          description="Access is matter-level and tied to a verified login, not a toggle anyone can flip. A walled matter is invisible in search, library, and lineage to anyone not on its list."
        />
        <BentoCard
          wide
          icon={<ReasonGlyph />}
          name="See why, not just what"
          description="Every result explains itself: why it ranked, why an outdated version was rejected, or why it's restricted — never a silent drop."
        />
        <BentoCard
          icon={<LineageGlyph />}
          name="Version history, mapped"
          description="Documents from the same matter are clustered automatically, with the current version at the hub and every superseded draft explained."
        />
        <BentoCard
          icon={<CiteGlyph />}
          name="Draft with citations"
          description="Generate a first draft strictly from the sources you select — every clause traces back to its exact source document and excerpt, and anything the sources don't cover is flagged as a gap instead of invented."
        />
        </BentoGrid>
      </div>

      {(onGoToLibrary || onGoToSearch) && (
        <div className="start-here-actions">
          {onGoToLibrary && (
            <button className="btn btn-primary" onClick={onGoToLibrary}>
              Go to Library
            </button>
          )}
          {onGoToSearch && (
            <button className="btn btn-primary" onClick={onGoToSearch}>
              Go to Search &amp; Draft
            </button>
          )}
        </div>
      )}

      <div className="section-label start-here-feature-heading">
        Best precedents from the firm
      </div>
      <p className="start-here-feature-intro">
        New to the team, or just picking up something outside your usual practice area? This is
        the firm's collective best work, organized so you don't have to already know where to
        look.
      </p>

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
          <div className="section-label start-here-subheading">Most relied upon firm-wide</div>
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
