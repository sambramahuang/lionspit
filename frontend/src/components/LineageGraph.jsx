import React, { useEffect, useState } from "react";
import { api } from "../api.js";

// Fixed-unit layout, no DOM measurement: the true version chain (draft ->
// redlined -> final, etc.) runs left-to-right ending at the current
// document; every other same-matter document (correspondence, billing,
// file notes -- connected via a "related" edge, not a "version" one)
// stacks in a column to the left of the chain and fans into it with a
// dashed curve. Deterministic and legible at hackathon-corpus scale (a
// handful of nodes per matter) -- no force layout, nothing to settle, and
// -- critically -- bounded to (related-column) + (chain-length) columns
// wide instead of one node per document, so it doesn't blow past the page
// width the way a flat one-row-per-document layout does once a matter has
// more than 3-4 documents.
// Sized so the common case -- a 3-hop version chain (draft -> redlined ->
// final) plus a related-documents column -- fits inside main.content's
// max-width (1180px) minus its own padding and .lineage-cluster's padding
// on top of that (effective ~1080px budget) at 1:1 scale. Matters with a
// longer chain than that are scaled down as a whole (see `scale` below)
// rather than left to overflow into a horizontal scrollbar.
const NODE_W = 200;
const NODE_H = 78;
const COL_GAP = 60;
const ROW_GAP = 16;
const ROW_H = NODE_H + ROW_GAP;
const DIAGRAM_BUDGET_W = 1080;
// Must match .lineage-diagram's padding-top in styles.css (reserves room
// for the "current"/"superseded" badges, which poke above the topmost
// node via a negative `top` offset). box-sizing is border-box project-wide,
// so this has to be added back into the height set below or that padding
// eats into the content box and clips the diagram's bottom edge instead.
const DIAGRAM_PADDING_TOP = 12;

function LineageNodeCard({ node, x, y, current, superseded, onPreview }) {
  const m = node.metadata || {};
  const tone = current ? "lineage-node-current" : superseded ? "lineage-node-superseded" : "";
  return (
    <div
      className={`lineage-node ${tone}`}
      style={{ left: x, top: y, width: NODE_W, height: NODE_H }}
    >
      <div>
        <div className="lineage-node-title">{node.filename}</div>
        <div className="lineage-node-meta">
          {[m.version, m.document_date, m.partner_approved && "partner-approved"]
            .filter(Boolean)
            .join(" · ") || "metadata not detected"}
        </div>
      </div>
      <button
        type="button"
        className="btn btn-ghost preview-btn lineage-preview-btn"
        onClick={() => onPreview?.(node.doc_id)}
      >
        Preview
      </button>
    </div>
  );
}

// Walks "version" edges backward from the current document to recover the
// ordered chain (oldest -> ... -> current). "related" edges never
// contribute a step here -- they connect a document to the matter, not to
// a specific earlier/later version of it.
function buildVersionChain(cluster) {
  const predecessor = {};
  for (const edge of cluster.edges) {
    if (edge.relation !== "related") predecessor[edge.to_doc_id] = edge.from_doc_id;
  }
  const chain = [cluster.current_doc_id];
  let cursor = cluster.current_doc_id;
  while (predecessor[cursor] && !chain.includes(predecessor[cursor])) {
    cursor = predecessor[cursor];
    chain.unshift(cursor);
  }
  return chain;
}

function ClusterDiagram({ cluster, onPreview }) {
  const nodeById = Object.fromEntries(cluster.nodes.map((n) => [n.doc_id, n]));
  const chainIds = buildVersionChain(cluster);
  const chainIdSet = new Set(chainIds);
  const chainNodes = chainIds.map((id) => nodeById[id]).filter(Boolean);
  const relatedNodes = cluster.nodes.filter((n) => !chainIdSet.has(n.doc_id));
  const reasonByDoc = Object.fromEntries(cluster.edges.map((e) => [e.from_doc_id, e.reason]));

  const relatedColX = 0;
  const chainStartX = relatedNodes.length > 0 ? NODE_W + COL_GAP : 0;
  const chainY = Math.max(relatedNodes.length, 1) * ROW_H / 2 - NODE_H / 2 - ROW_GAP / 2;
  const svgHeight = Math.max(relatedNodes.length * ROW_H, NODE_H);
  const svgWidth = chainStartX + chainNodes.length * NODE_W + Math.max(chainNodes.length - 1, 0) * COL_GAP;
  const currentX = chainStartX + (chainNodes.length - 1) * (NODE_W + COL_GAP);
  const scale = svgWidth > DIAGRAM_BUDGET_W ? DIAGRAM_BUDGET_W / svgWidth : 1;

  return (
    <div className="lineage-cluster">
      <div className="lineage-cluster-label">
        {cluster.label} <span className="count">{cluster.nodes.length}</span>
      </div>

      <div className="lineage-diagram" style={{ height: svgHeight * scale + DIAGRAM_PADDING_TOP }}>
        <div style={{ width: svgWidth, height: svgHeight, transform: `scale(${scale})`, transformOrigin: "top left" }}>
          <svg width={svgWidth} height={svgHeight} className="lineage-svg">
            <defs>
              <marker id={`arrow-${cluster.key}`} markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
                <path d="M0,0 L6,3 L0,6 Z" fill="var(--ink)" />
              </marker>
            </defs>

            {/* Solid links: consecutive members of the same document's own version chain. */}
            {chainNodes.slice(1).map((node, i) => {
              const fromX = chainStartX + i * (NODE_W + COL_GAP) + NODE_W;
              const toX = chainStartX + (i + 1) * (NODE_W + COL_GAP);
              return (
                <path
                  key={`chain-${node.doc_id}`}
                  d={`M ${fromX} ${chainY + NODE_H / 2} L ${toX - 6} ${chainY + NODE_H / 2}`}
                  stroke="var(--rule)"
                  strokeWidth="1.5"
                  fill="none"
                  markerEnd={`url(#arrow-${cluster.key})`}
                />
              );
            })}

            {/* Dashed links: other same-matter documents fanning into the current version. */}
            {relatedNodes.map((node, i) => {
              const y0 = i * ROW_H + NODE_H / 2;
              const y1 = chainY + NODE_H / 2;
              const midX = (NODE_W + currentX) / 2;
              return (
                <path
                  key={`related-${node.doc_id}`}
                  d={`M ${NODE_W} ${y0} C ${midX} ${y0}, ${midX} ${y1}, ${currentX - 6} ${y1}`}
                  stroke="var(--ink-softer)"
                  strokeWidth="1.5"
                  strokeDasharray="5 4"
                  fill="none"
                  markerEnd={`url(#arrow-${cluster.key})`}
                />
              );
            })}
          </svg>

          {relatedNodes.map((node, i) => (
            <LineageNodeCard
              key={node.doc_id}
              node={node}
              x={relatedColX}
              y={i * ROW_H}
              current={false}
              onPreview={onPreview}
            />
          ))}
          {chainNodes.map((node, i) => (
            <LineageNodeCard
              key={node.doc_id}
              node={node}
              x={chainStartX + i * (NODE_W + COL_GAP)}
              y={chainY}
              current={node.doc_id === cluster.current_doc_id}
              superseded={node.doc_id !== cluster.current_doc_id}
              onPreview={onPreview}
            />
          ))}
        </div>
      </div>

      <div className="lineage-reasons">
        {chainNodes.slice(0, -1).map((node) => (
          <div key={`${node.doc_id}-reason`} className="lineage-reason-row">
            <span className="lineage-reason-file">{node.filename}</span>
            <span className="reason-text" style={{ margin: 0 }}>{reasonByDoc[node.doc_id]}</span>
          </div>
        ))}
        {relatedNodes.map((node) => (
          <div key={`${node.doc_id}-reason`} className="lineage-reason-row">
            <span className="lineage-reason-file">{node.filename}</span>
            <span className="relevance-text" style={{ margin: 0 }}>{reasonByDoc[node.doc_id]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function LineageGraph({ refreshKey, onPreview }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.lineage()
      .then((res) => { if (!cancelled) setData(res); })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  if (loading) return <p className="spinner-text">Loading lineage...</p>;
  if (error) return <div className="error-banner">{error}</div>;

  if (!data || data.clusters.length === 0) {
    return (
      <div className="empty-state">
        No version history to show yet — a lineage forms once two or more
        documents belong to the same matter.
      </div>
    );
  }

  return (
    <div>
      {data.clusters.map((cluster) => (
        <ClusterDiagram key={cluster.key} cluster={cluster} onPreview={onPreview} />
      ))}

      {data.standalone.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div className="section-label">
            Standalone documents <span className="count">{data.standalone.length}</span>
          </div>
          <p style={{ fontSize: 12.5, color: "var(--text-muted)", margin: "0 0 10px" }}>
            This document is currently the only indexed document in its matter,
            so there are no relationships to draw yet.
          </p>
          <div className="lineage-standalone-grid">
            {data.standalone.map((node) => (
              <div key={node.doc_id} className="lineage-standalone-item">
                <span className="lineage-standalone-name">{node.filename}</span>
                <button
                  type="button"
                  className="btn btn-ghost preview-btn"
                  onClick={() => onPreview?.(node.doc_id)}
                >
                  Preview
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
