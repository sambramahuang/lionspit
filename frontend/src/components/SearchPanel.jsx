import React from "react";

const WEIGHT_LABELS = {
  similarity: "Similarity to query",
  recency: "Recency",
  frequency: "Firm usage frequency",
  partner_approval: "Partner approval",
  jurisdiction_match: "Jurisdiction match",
};

export default function SearchPanel({
  query, setQuery,
  jurisdictionFilter, setJurisdictionFilter,
  matterTypeFilter, setMatterTypeFilter,
  weights, setWeights,
  clearance, setClearance,
  onSearch, busy,
}) {
  const updateWeight = (key, value) => {
    setWeights((prev) => ({ ...prev, [key]: parseFloat(value) }));
  };

  return (
    <div className="card">
      <div className="search-row">
        <div className="search-input-wrap">
          <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            className="search-input"
            placeholder='Describe what you need — legal terms or plain English both work, e.g. "cap on founder liability in a shareholders agreement"'
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onSearch()}
          />
        </div>
        <button className="btn btn-brass" onClick={onSearch} disabled={busy || !query.trim()}>
          {busy ? "Searching..." : "Search"}
        </button>
      </div>

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
        <select
          className="filter-input"
          style={{ width: 200 }}
          value={clearance}
          onChange={(e) => setClearance(e.target.value)}
        >
          <option value="standard">Viewer: standard access</option>
          <option value="elevated">Viewer: elevated access</option>
        </select>
      </div>

      <div className="section-label" style={{ margin: "18px 0 4px" }}>Ranking weights</div>
      <div className="weights-panel">
        {Object.entries(weights).map(([key, value]) => (
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
    </div>
  );
}
