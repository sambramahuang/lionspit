import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import UploadPanel from "./components/UploadPanel.jsx";
import DocumentLibrary from "./components/DocumentLibrary.jsx";
import SearchPage from "./components/SearchPage.jsx";

export default function App() {
  const [tab, setTab] = useState("library");
  const [apiUp, setApiUp] = useState(null);
  const [docCount, setDocCount] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);

  const checkHealth = async () => {
    try {
      const res = await api.health();
      setApiUp(true);
      setDocCount(res.documents_indexed);
    } catch {
      setApiUp(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, [refreshKey]);

  const bumpRefresh = () => setRefreshKey((k) => k + 1);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-name">Precedent Bank</span>
          <span className="brand-tag">MVP · The Lion's Pit 2026</span>
        </div>
        <nav className="tabs">
          <button
            className={`tab-btn ${tab === "library" ? "active" : ""}`}
            onClick={() => setTab("library")}
          >
            Library
          </button>
          <button
            className={`tab-btn ${tab === "search" ? "active" : ""}`}
            onClick={() => setTab("search")}
          >
            Search &amp; Draft
          </button>
        </nav>
        <div className="status-pill">
          <span className={`status-dot ${apiUp === false ? "down" : ""}`} />
          {apiUp === null && "checking API..."}
          {apiUp === true && `API online · ${docCount} docs indexed`}
          {apiUp === false && "API offline — start the backend on :8000"}
        </div>
      </header>

      <main className="content">
        {tab === "library" && (
          <>
            <div className="page-header">
              <h1 className="page-title">Document library</h1>
              <p className="page-subtitle">
                Drop in messy files as-is. Each one is read, described, and
                tagged automatically — no manual sorting or metadata entry
                required before it becomes searchable.
              </p>
            </div>
            <UploadPanel onIngested={bumpRefresh} />
            <div style={{ height: 28 }} />
            <DocumentLibrary refreshKey={refreshKey} onReset={bumpRefresh} />
          </>
        )}

        {tab === "search" && <SearchPage />}
      </main>
    </div>
  );
}
