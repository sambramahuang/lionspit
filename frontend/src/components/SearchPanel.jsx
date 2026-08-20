import React, { useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { api } from "../api.js";

// Caps how much of an attached document's text gets folded into the
// query -- consistent with ingestion.py's own 6000-char excerpt cap for
// the metadata LLM. Long enough for a real fact pattern or case summary,
// short enough to keep embedding cost/latency and the LLM relevance pass
// bounded regardless of how long the source document actually is.
const MAX_ATTACHED_CONTEXT_CHARS = 6000;

// Hardcoded example queries grounded in documents actually in the seeded
// corpus (case_documents/) -- rotated randomly instead of one static
// example, so the placeholder doesn't quietly go stale/unbelievable if the
// corpus changes, and so it demonstrates a wider slice of what the search
// actually finds rather than always showing the same one query.
const DOCUMENT_QUERY_EXAMPLES = [
  "application for specific production of QA defect logs in a supply contract dispute",
  "specific production of bunker fuel delivery and lab test records",
  "board seat threshold for a Series B investor",
  "royalty rate in a trademark licensing agreement",
  "vacant possession clause in a residential sale and purchase agreement",
  "anti-dilution protection on a down round",
  "non-compete restriction on a licensee",
  "quality control and inspection rights over a licensed brand",
];

const CLAUSE_QUERY_EXAMPLES = [
  "threshold for specific production under Order 11 Rule 3",
  "broad-based weighted average anti-dilution formula",
  "tag-along and drag-along rights at 75%",
  "time being of the essence for completion",
  "quality control inspection rights for a licensor",
  "royalty rate increasing from year 3 onward",
];

function pickRandom(list) {
  return list[Math.floor(Math.random() * list.length)];
}

// Matches the app's icon language elsewhere (App.jsx's ICON_PROPS,
// BentoGrid's glyphs) -- thin-stroke line icon, not an emoji.
function AttachIcon() {
  return (
    <svg
      width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"
      style={{ verticalAlign: -2 }}
    >
      <path d="M21.44 11.05l-9.19 9.19a5 5 0 0 1-7.07-7.07l9.19-9.19a3.5 3.5 0 0 1 4.95 4.95l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
    </svg>
  );
}

const WEIGHT_LABELS = {
  similarity: "Similarity to query",
  frequency: "Firm usage frequency",
  partner_approval: "Partner approval",
  jurisdiction_match: "Jurisdiction match",
};

const RECENCY_OPTIONS = [
  ["30d", "Past 30 days"], ["6m", "Past 6 months"], ["1y", "Past 1 year"],
  ["3y", "Past 3 years"], ["5y", "Past 5 years"],
];
const STATUS_OPTIONS = ["In force", "Repealed", "Amending/ overruled"];
const DOCUMENT_TYPE_OPTIONS = [
  "Cases / Judgments", "Legislation", "Regulations", "Contracts / Agreements",
  "Legal opinions", "Pleadings", "Firm precedents", "Other",
];

export default function SearchPanel({
  query, setQuery,
  attachedContexts, onAttachedContextsChange,
  jurisdictionFilter, setJurisdictionFilter,
  matterTypeFilter, setMatterTypeFilter,
  recencyFilter, setRecencyFilter,
  statusFilters, setStatusFilters,
  documentTypeFilters, setDocumentTypeFilters,
  weights, setWeights,
  mode, setMode,
  onSearch, busy,
}) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [attaching, setAttaching] = useState(false);
  const [attachError, setAttachError] = useState(null);
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);

  const updateWeight = (key, value) => {
    setWeights((prev) => ({ ...prev, [key]: parseFloat(value) }));
  };

  const toggleFilter = (setter, value) => {
    setter((prev) => prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value]);
  };

  // Re-rolled whenever `mode` changes (including the first render) -- not
  // on every keystroke, which would make the placeholder flicker while
  // the field is empty and focused.
  const placeholderExample = useMemo(
    () => pickRandom(mode === "clauses" ? CLAUSE_QUERY_EXAMPLES : DOCUMENT_QUERY_EXAMPLES),
    [mode]
  );

  // Auto-grows with content (up to a scrollable cap in CSS) instead of a
  // fixed-height box, so pasting in a page of case facts doesn't get
  // squeezed into a one-line field -- reset to "auto" first or the box
  // would only ever grow, never shrink back down after deleting text.
  const autoResize = (el) => {
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  };

  const handleAttachClick = () => fileInputRef.current?.click();

  const handleFileSelected = async (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = ""; // allow re-selecting the same file(s) later
    if (!files.length) return;
    setAttachError(null);
    setAttaching(true);
    try {
      const extracted = await Promise.all(files.map(async (file) => {
        const res = await api.extractText(file);
        const text = res.text.length > MAX_ATTACHED_CONTEXT_CHARS
          ? res.text.slice(0, MAX_ATTACHED_CONTEXT_CHARS) + "…"
          : res.text;
        return { id: crypto.randomUUID(), filename: res.filename, text };
      }));
      onAttachedContextsChange?.([...(attachedContexts || []), ...extracted]);
    } catch (err) {
      setAttachError(err.message);
    } finally {
      setAttaching(false);
    }
  };

  const removeAttachedContext = (id) => {
    onAttachedContextsChange?.((attachedContexts || []).filter((doc) => doc.id !== id));
  };

  return (
    <div className="card">
      <div className="view-toggle" style={{ marginBottom: 14 }}>
        <button
          className={`view-toggle-btn ${mode === "documents" ? "active" : ""}`}
          onClick={() => setMode("documents")}
        >
          Search documents
        </button>
        <button
          className={`view-toggle-btn ${mode === "clauses" ? "active" : ""}`}
          onClick={() => setMode("clauses")}
        >
          Search clauses
        </button>
      </div>

      <div className="search-row">
        <div className="search-input-wrap">
          <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <textarea
            ref={textareaRef}
            className="search-input search-input-expandable"
            rows={1}
            placeholder={`e.g. "${placeholderExample}"`}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              autoResize(e.target);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSearch();
              }
            }}
          />
        </div>
        <button className="btn btn-primary" onClick={onSearch} disabled={busy || (!query.trim() && !attachedContexts?.length)}>
          {busy ? "Searching..." : "Search"}
        </button>
      </div>

      <p className="search-hint">
        Legal terms or plain English both work — paste in as much context as you want (the facts
        of the matter you're working on), not just a short phrase.
      </p>

      <div className="search-attach-row">
        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.docx,.pdf"
          multiple
          style={{ display: "none" }}
          onChange={handleFileSelected}
        />
        <button
          type="button"
          className="btn btn-ghost search-attach-btn"
          onClick={handleAttachClick}
          disabled={attaching}
        >
          {attaching
            ? "Reading document..."
            : attachedContexts?.length
              ? "Attach another document"
              : "Attach a document for context"}
        </button>
        {attachedContexts?.map((doc) => (
          <span className="search-attach-chip" key={doc.id}>
            <AttachIcon /> {doc.filename}
            <button
              type="button"
              aria-label={`Remove ${doc.filename}`}
              onClick={() => removeAttachedContext(doc.id)}
            >
              ×
            </button>
          </span>
        ))}
        {attachError && <span className="reason-text" style={{ margin: 0 }}>{attachError}</span>}

        <button
          type="button"
          className="btn btn-ghost search-advanced-toggle"
          onClick={() => setShowAdvanced((v) => !v)}
          aria-expanded={showAdvanced}
        >
          Filters &amp; weights
        </button>
      </div>

      <AnimatePresence initial={false}>
        {showAdvanced && (
          <motion.div
            key="advanced"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
            style={{ overflow: "hidden" }}
          >
            <div style={{ paddingTop: 14 }}>
              {mode === "documents" && (
                <>
                  <div className="filters-row">
                    <input
                      className="filter-input"
                      placeholder="Jurisdiction filter (optional)"
                      value={jurisdictionFilter}
                      onChange={(e) => setJurisdictionFilter(e.target.value)}
                    />
                    <input
                      className="filter-input"
                      placeholder="Matter type filter (optional)"
                      value={matterTypeFilter}
                      onChange={(e) => setMatterTypeFilter(e.target.value)}
                    />
                  </div>

                  <div className="filter-checklists">
                    <fieldset className="filter-checklist">
                      <legend>Recency</legend>
                      {RECENCY_OPTIONS.map(([value, label]) => (
                        <label key={value}><input type="radio" name="recency" checked={recencyFilter === value} onChange={() => setRecencyFilter(value)} />{label}</label>
                      ))}
                      <label><input type="radio" name="recency" checked={!recencyFilter} onChange={() => setRecencyFilter("")} />Any time</label>
                    </fieldset>
                    <fieldset className="filter-checklist">
                      <legend>Status category</legend>
                      {STATUS_OPTIONS.map((value) => (
                        <label key={value}><input type="checkbox" checked={statusFilters.includes(value)} onChange={() => toggleFilter(setStatusFilters, value)} />{value}</label>
                      ))}
                    </fieldset>
                    <fieldset className="filter-checklist">
                      <legend>Document Type</legend>
                      {DOCUMENT_TYPE_OPTIONS.map((value) => (
                        <label key={value}><input type="checkbox" checked={documentTypeFilters.includes(value)} onChange={() => toggleFilter(setDocumentTypeFilters, value)} />{value}</label>
                      ))}
                    </fieldset>
                  </div>
                </>
              )}

              <div className="section-label" style={{ margin: "18px 0 4px", fontSize: 16, color: "black" }}>
                Customize weights
              </div>
              <div className="weights-panel">
                {Object.entries(weights).filter(([key]) => key !== "recency").map(([key, value]) => (
                  <div className="weight-row" key={key}>
                    <label>
                      <span>{WEIGHT_LABELS[key] || key}</span>
                      <span className="weight-value">{value.toFixed(2)}</span>
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={value}
                      onChange={(e) => updateWeight(key, e.target.value)}
                    />
                  </div>
                ))}
              </div>

              {mode === "clauses" && (
                <p style={{ fontSize: 12.5, color: "var(--text-muted)", margin: "14px 0 0" }}>
                  Matches individual clauses across every document, not whole documents — useful when you
                  know the provision you need but not which agreement it's in.
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
