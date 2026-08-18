import React, { useEffect, useState } from "react";
import { api } from "../api.js";

function EmailListEditor({ emails, onChange }) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const v = draft.trim().toLowerCase();
    if (v) onChange([...new Set([...emails, v])]);
    setDraft("");
  };
  return (
    <div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 6 }}>
        {emails.map((e) => (
          <span key={e} className="badge badge-unapproved">
            {e}
            <button
              type="button"
              style={{ marginLeft: 6, border: "none", background: "none", cursor: "pointer", color: "inherit" }}
              onClick={() => onChange(emails.filter((x) => x !== e))}
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <input
        className="filter-input"
        placeholder="Add email, press Enter"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            add();
          }
        }}
      />
    </div>
  );
}

export default function MattersView({ isPartner }) {
  const [matters, setMatters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(null);
  const [acking, setAcking] = useState(null);

  const load = () => {
    setLoading(true);
    setError(null);
    api.listMatters().then(setMatters).catch((e) => setError(e.message)).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const patch = (key, fn) =>
    setMatters((prev) => prev.map((m) => (m.matter_key === key ? { ...m, wall: fn(m.wall) } : m)));

  const save = async (m) => {
    setSaving(m.matter_key);
    setError(null);
    try {
      const updated = await api.setMatterWall(m.matter_key, {
        walled: m.wall.walled,
        allowed_emails: m.wall.allowed_emails,
      });
      patch(m.matter_key, () => updated);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(null);
    }
  };

  const acknowledge = async (matterKey) => {
    setAcking(matterKey);
    setError(null);
    try {
      const updated = await api.acknowledgeConflict(matterKey);
      setMatters((prev) => prev.map((m) => (m.matter_key === matterKey ? { ...m, conflict: updated } : m)));
    } catch (e) {
      setError(e.message);
    } finally {
      setAcking(null);
    }
  };

  const header = (
    <div className="page-header">
      <h1 className="page-title">Matters</h1>
      <p className="page-subtitle">
        Every matter the corpus has enough signal to cluster, with its ethical-wall status and any
        automatically detected conflict of interest. Partners can wall a matter or acknowledge a
        conflict flag here — everyone else sees status only. Conflicts are never applied
        automatically; a partner always makes the call.
      </p>
    </div>
  );

  if (loading) {
    return (
      <>
        {header}
        <p className="spinner-text">Loading matters...</p>
      </>
    );
  }
  if (error) {
    return (
      <>
        {header}
        <div className="error-banner">{error}</div>
      </>
    );
  }
  if (matters.length === 0) {
    return (
      <>
        {header}
        <div className="empty-state">
          No matters yet — a matter forms once two or more documents share the same named parties and matter type.
        </div>
      </>
    );
  }

  return (
    <>
      {header}

      <div className="card">
        <div className="section-label">
          Matters <span className="count">{matters.length}</span>
        </div>
        <div style={{ overflowX: "auto" }}>
        <table className="doc-table">
          <thead>
            <tr>
              <th>Matter</th>
              <th>Docs</th>
              <th>Wall</th>
              <th>Allowed viewers</th>
              <th>Conflict</th>
              {isPartner && <th></th>}
            </tr>
          </thead>
          <tbody>
            {matters.map((m) => {
              const unresolvedConflict = m.conflict && !m.conflict.acknowledged;
              return (
                <tr key={m.matter_key} className={unresolvedConflict ? "matter-row-conflict" : ""}>
                  <td>{m.label}</td>
                  <td className="mono">{m.document_count}</td>
                  <td>
                    {isPartner ? (
                      <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <input
                          type="checkbox"
                          checked={m.wall.walled}
                          onChange={(e) => patch(m.matter_key, (w) => ({ ...w, walled: e.target.checked }))}
                        />
                        walled
                      </label>
                    ) : m.wall.walled ? (
                      <span className="badge badge-restricted">walled</span>
                    ) : (
                      <span className="mono" style={{ color: "var(--text-muted)" }}>open</span>
                    )}
                  </td>
                  <td>
                    {isPartner ? (
                      <EmailListEditor
                        emails={m.wall.allowed_emails}
                        onChange={(emails) => patch(m.matter_key, (w) => ({ ...w, allowed_emails: emails }))}
                      />
                    ) : (
                      m.wall.allowed_emails.join(", ") || "—"
                    )}
                  </td>
                  <td style={{ maxWidth: 260 }}>
                    {!m.conflict ? (
                      <span className="mono" style={{ color: "var(--text-muted)" }}>—</span>
                    ) : unresolvedConflict ? (
                      <div>
                        <span className="badge badge-conflict">possible conflict</span>
                        <p className="reason-text" style={{ marginTop: 5 }}>{m.conflict.reason}</p>
                        {isPartner && (
                          <button
                            type="button"
                            className="btn btn-ghost"
                            style={{ marginTop: 6 }}
                            disabled={acking === m.matter_key}
                            onClick={() => acknowledge(m.matter_key)}
                          >
                            {acking === m.matter_key ? "Saving..." : "Acknowledge"}
                          </button>
                        )}
                      </div>
                    ) : (
                      <span className="badge badge-unapproved">
                        reviewed{m.conflict.acknowledged_by ? ` by ${m.conflict.acknowledged_by}` : ""}
                      </span>
                    )}
                  </td>
                  {isPartner && (
                    <td>
                      <button className="btn btn-ghost" disabled={saving === m.matter_key} onClick={() => save(m)}>
                        {saving === m.matter_key ? "Saving..." : "Save"}
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
        </div>
      </div>
    </>
  );
}
