import React, { useRef, useState } from "react";
import { api } from "../api.js";
import SearchPanel from "./SearchPanel.jsx";
import ResultCard from "./ResultCard.jsx";
import DraftView from "./DraftView.jsx";

const DEFAULT_WEIGHTS = {
  similarity: 0.4,
  recency: 0.15,
  frequency: 0.15,
  partner_approval: 0.2,
  jurisdiction_match: 0.1,
};

export default function SearchPage({ onPreview }) {
  const [query, setQuery] = useState("");
  const [jurisdictionFilter, setJurisdictionFilter] = useState("");
  const [matterTypeFilter, setMatterTypeFilter] = useState("");
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [showOther, setShowOther] = useState(false);
  const [highlighted, setHighlighted] = useState(null);

  const cardRefs = useRef({});

  const runSearch = async () => {
    if (!query.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.search({
        query,
        jurisdiction_filter: jurisdictionFilter || null,
        matter_type_filter: matterTypeFilter || null,
        weights,
      });
      setResult(res);
      setSelectedIds(res.kept.map((k) => k.doc_id));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const toggleSelect = (docId) => {
    setSelectedIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  const jumpToSource = (docId) => {
    setShowOther(true);
    setHighlighted(docId);
    const node = cardRefs.current[docId];
    if (node) node.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(() => setHighlighted(null), 1600);
  };

  const previewAndHighlight = (docId) => {
    onPreview?.(docId);
    setHighlighted(docId);
    setTimeout(() => setHighlighted(null), 1600);
  };

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Search &amp; draft</h1>
        <p className="page-subtitle">
          Every result explains itself: why it ranked, why anything was
          rejected or restricted, and — once you draft — exactly which
          document each clause came from.
        </p>
      </div>

      <SearchPanel
        query={query} setQuery={setQuery}
        jurisdictionFilter={jurisdictionFilter} setJurisdictionFilter={setJurisdictionFilter}
        matterTypeFilter={matterTypeFilter} setMatterTypeFilter={setMatterTypeFilter}
        weights={weights} setWeights={setWeights}
        onSearch={runSearch} busy={busy}
      />

      {error && <div className="error-banner" style={{ marginTop: 16 }}>{error}</div>}

      {result && (
        <>
          <div className="section-label">
            Selected as strongest precedents <span className="count">{result.kept.length}</span>
          </div>
          <div className="result-grid">
            {result.kept.map((item) => (
              <ResultCard
                key={item.doc_id}
                item={item}
                tone="kept"
                reason={item.llm_relevance_reason}
                selectable
                selected={selectedIds.includes(item.doc_id)}
                onToggle={toggleSelect}
                onPreview={previewAndHighlight}
                sourceRef={(el) => (cardRefs.current[item.doc_id] = el)}
                highlighted={highlighted === item.doc_id}
              />
            ))}
            {result.kept.length === 0 && (
              <div className="empty-state">Nothing cleared the bar as a top precedent for this query.</div>
            )}
          </div>

          {result.rejected.length > 0 && (
            <>
              <div className="section-label">
                Rejected <span className="count">{result.rejected.length}</span>
              </div>
              <div className="result-grid">
                {result.rejected.map((item) => (
                  <ResultCard
                    key={item.doc_id}
                    item={item}
                    tone="rejected"
                    reason={item.reason}
                    onPreview={previewAndHighlight}
                    sourceRef={(el) => (cardRefs.current[item.doc_id] = el)}
                    highlighted={highlighted === item.doc_id}
                  />
                ))}
              </div>
            </>
          )}

          {result.access_restricted.length > 0 && (
            <>
              <div className="section-label">
                Access restricted <span className="count">{result.access_restricted.length}</span>
              </div>
              <div className="result-grid">
                {result.access_restricted.map((item) => (
                  <ResultCard key={item.doc_id} item={item} tone="restricted" reason={item.reason} />
                ))}
              </div>
            </>
          )}

          {result.other_candidates.length > 0 && (
            <>
              <div
                className="section-label"
                style={{ cursor: "pointer" }}
                onClick={() => setShowOther((s) => !s)}
              >
                {showOther ? "▾" : "▸"} Other candidates considered
                <span className="count">{result.other_candidates.length}</span>
              </div>
              {showOther && (
                <div className="result-grid">
                  {result.other_candidates.map((item) => (
                    <ResultCard
                      key={item.doc_id}
                      item={item}
                      tone="neutral"
                      reason={item.llm_relevance_reason}
                      selectable
                      selected={selectedIds.includes(item.doc_id)}
                      onToggle={toggleSelect}
                      onPreview={previewAndHighlight}
                      sourceRef={(el) => (cardRefs.current[item.doc_id] = el)}
                      highlighted={highlighted === item.doc_id}
                    />
                  ))}
                </div>
              )}
            </>
          )}

          <DraftView query={query} selectedDocIds={selectedIds} onCiteClick={jumpToSource} />
        </>
      )}
    </>
  );
}
