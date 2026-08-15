import React, { useEffect, useState } from "react";
import { api } from "../api.js";

// Fixed-unit layout, no DOM measurement: history nodes stack in a left
// column, the current document sits in a right column vertically centered
// against that stack, and an SVG curve with an arrowhead connects each
// history node to it. Deterministic and legible at hackathon-corpus scale
// (a handful of nodes per matter) -- no force layout, nothing to settle.
const NODE_W = 230;
const NODE_H = 78;
const COL_GAP = 110;
const ROW_GAP = 16;
const ROW_H = NODE_H + ROW_GAP;

function LineageNodeCard({ node, x, y, current, onPreview }) {
  const m = node.metadata || {};
  return (
    <div
      className={`lineage-node ${current ? "lineage-node-current" : ""}`}
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

function ClusterDiagram({ cluster, onPreview }) {
  const current = cluster.nodes.find((n) => n.doc_id === cluster.current_doc_id);
  const history = cluster.nodes.filter((n) => n.doc_id !== cluster.current_doc_id);
  const reasonByDoc = Object.fromEntries(cluster.edges.map((e) => [e.from_doc_id, e.reason]));

  const rows = Math.max(history.length, 1);
  const svgHeight = rows * ROW_H;
  const currentX = NODE_W + COL_GAP;
  const currentY = svgHeight / 2 - NODE_H / 2;
  const svgWidth = currentX + NODE_W;

  return (
    <div className="lineage-cluster">
      <div className="lineage-cluster-label">
        {cluster.label} <span className="count">{cluster.nodes.length}</span>
      </div>

      <div className="lineage-diagram" style={{ height: svgHeight, minWidth: svgWidth }}>
        <svg width={svgWidth} height={svgHeight} className="lineage-svg">
          <defs>
            <marker id={`arrow-${cluster.key}`} markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
              <path d="M0,0 L6,3 L0,6 Z" fill="var(--brass)" />
            </marker>
          </defs>
          {history.map((node, i) => {
            const y0 = i * ROW_H + NODE_H / 2;
            const y1 = currentY + NODE_H / 2;
            const midX = (NODE_W + currentX) / 2;
            return (
              <path
                key={node.doc_id}
                d={`M ${NODE_W} ${y0} C ${midX} ${y0}, ${midX} ${y1}, ${currentX - 6} ${y1}`}
                stroke="var(--rule)"
                strokeWidth="1.5"
                fill="none"
                markerEnd={`url(#arrow-${cluster.key})`}
              />
            );
          })}
        </svg>

        {history.map((node, i) => (
          <LineageNodeCard key={node.doc_id} node={node} x={0} y={i * ROW_H} current={false} onPreview={onPreview} />
        ))}
        {current && (
          <LineageNodeCard node={current} x={currentX} y={currentY} current onPreview={onPreview} />
        )}
      </div>

      <div className="lineage-reasons">
        {history.map((node) => (
          <div key={node.doc_id} className="lineage-reason-row">
            <span className="lineage-reason-file">{node.filename}</span>
            <span className="reason-text" style={{ margin: 0 }}>{reasonByDoc[node.doc_id]}</span>
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
        documents share the same named parties and matter type.
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
            No other version shares this document's named parties and matter
            type, so there's no lineage to draw.
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
