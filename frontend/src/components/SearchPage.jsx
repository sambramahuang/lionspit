import React, { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import SearchPanel from "./SearchPanel.jsx";
import ResultCard from "./ResultCard.jsx";
import ClauseResultCard from "./ClauseResultCard.jsx";
import DraftView from "./DraftView.jsx";

const DEFAULT_WEIGHTS = {
  similarity: 0.5,
  frequency: 0.5,
  partner_approval: 0.5,
  jurisdiction_match: 0.5,
};

export default function SearchPage({ onPreview }) {
  const [mode, setMode] = useState("documents"); // "documents" | "clauses"
  const [query, setQuery] = useState("");
  const [jurisdictionFilter, setJurisdictionFilter] = useState("");
  const [matterTypeFilter, setMatterTypeFilter] = useState("");
  const [recencyFilter, setRecencyFilter] = useState("");
  // Empty = unfiltered, matching every other filter here (jurisdiction,
  // matter type, recency) and search.py's own convention (`if
  // req.status_filters:` only applies the filter when non-empty). Defaulting
  // these to "every option pre-checked" instead looks equivalent in the UI
  // but isn't: search.py then filters for metadata.status/document_type
  // being IN that list, and most of the corpus predates these two fields
  // entirely (status is unset, document_type is free-text from the older
  // ingestion prompt) -- so a "fully checked" default silently excluded
  // every document from every search.
  const [statusFilters, setStatusFilters] = useState([]);
  const [documentTypeFilters, setDocumentTypeFilters] = useState([]);
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [clauseResult, setClauseResult] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [showOther, setShowOther] = useState(false);
  const [highlighted, setHighlighted] = useState(null);

  const cardRefs = useRef({});
  const resultsRef = useRef(null);

  useEffect(() => {
    if (!result && !clauseResult) return;

    const target = resultsRef.current;
    if (!target) return;
    const targetY = target.getBoundingClientRect().top + window.scrollY;
    const startY = window.scrollY;
    const distance = targetY - startY;
    const duration = 1200;
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    if (reduceMotion || Math.abs(distance) < 4) {
      window.scrollTo({ top: targetY, left: 0, behavior: "auto" });
      return;
    }

    const root = document.documentElement;
    const previousScrollBehavior = root.style.scrollBehavior;
    // Disable the global CSS smooth-scroll rule while driving every frame
    // ourselves; otherwise each frame queues another browser animation.
    root.style.scrollBehavior = "auto";

    let frameId;
    const startTime = performance.now();
    const easeInOut = (progress) => {
      const eased = progress < 0.5
        ? 2 * progress * progress
        : 1 - Math.pow(-2 * progress + 2, 2) / 2;
      return eased;
    };
    const animateScroll = (now) => {
      const progress = Math.min((now - startTime) / duration, 1);
      window.scrollTo({
        top: startY + distance * easeInOut(progress),
        left: 0,
        behavior: "auto",
      });
      if (progress < 1) frameId = requestAnimationFrame(animateScroll);
    };
    frameId = requestAnimationFrame(animateScroll);

    return () => {
      cancelAnimationFrame(frameId);
      root.style.scrollBehavior = previousScrollBehavior;
    };
  }, [result, clauseResult]);

  const switchMode = (next) => {
    setMode(next);
    setResult(null);
    setClauseResult(null);
    setError(null);
  };

  const runSearch = async () => {
    if (!query.trim()) return;
    setBusy(true);
    setError(null);
    try {
      if (mode === "clauses") {
        const res = await api.searchClauses({ query, weights });
        setClauseResult(res);
        setSelectedIds([...new Set(res.kept.map((k) => k.doc_id))]);
      } else {
        const res = await api.search({
          query,
          jurisdiction_filter: jurisdictionFilter || null,
          matter_type_filter: matterTypeFilter || null,
          recency_filter: recencyFilter || null,
          status_filters: statusFilters,
          document_type_filters: documentTypeFilters,
          weights,
        });
        setResult(res);
        setSelectedIds(res.kept.map((k) => k.doc_id));
      }
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
        recencyFilter={recencyFilter} setRecencyFilter={setRecencyFilter}
        statusFilters={statusFilters} setStatusFilters={setStatusFilters}
        documentTypeFilters={documentTypeFilters} setDocumentTypeFilters={setDocumentTypeFilters}
        weights={weights} setWeights={setWeights}
        mode={mode} setMode={switchMode}
        onSearch={runSearch} busy={busy}
      />

      {error && <div className="error-banner" style={{ marginTop: 16 }}>{error}</div>}

      <div ref={resultsRef} className="search-results-anchor">
        {mode === "clauses" && clauseResult && (
          <>
          <div className="section-label">
            Matching clauses <span className="count">{clauseResult.kept.length}</span>
          </div>
          <div className="result-grid">
            {clauseResult.kept.map((item) => (
              <ClauseResultCard
                key={`${item.doc_id}-${item.clause_index}`}
                item={item}
                selectable
                selected={selectedIds.includes(item.doc_id)}
                onToggle={toggleSelect}
                onPreview={previewAndHighlight}
              />
            ))}
            {clauseResult.kept.length === 0 && (
              <div className="empty-state">No clauses matched that closely enough. Try rephrasing, or switch to document search.</div>
            )}
          </div>

          {clauseResult.access_restricted.length > 0 && (
            <div className="section-label" style={{ marginTop: 10 }}>
              <span className="restricted-text" style={{ marginTop: 0 }}>
                {clauseResult.access_restricted.length} matching clause(s) hidden by an ethical wall
              </span>
            </div>
          )}

          <DraftView query={query} selectedDocIds={selectedIds} onCiteClick={jumpToSource} />
          </>
        )}

        {mode === "documents" && result && (
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
              <p style={{ fontSize: 12.5, color: "var(--text-muted)", margin: "0 0 10px" }}>
                Flagged automatically — superseded, not partner-approved, or not relevant to this
                query. Nothing here is ever deleted or hidden from you: check the box to include
                one in the draft anyway if you know better than the flag.
              </p>
              <div className="result-grid">
                {result.rejected.map((item) => (
                  <ResultCard
                    key={item.doc_id}
                    item={item}
                    tone="rejected"
                    reason={item.reason}
                    selectable
                    selected={selectedIds.includes(item.doc_id)}
                    onToggle={toggleSelect}
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
      </div>
    </>
  );
}
