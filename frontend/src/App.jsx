import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import UploadPanel from "./components/UploadPanel.jsx";
import DocumentLibrary from "./components/DocumentLibrary.jsx";
import LineageGraph from "./components/LineageGraph.jsx";
import SearchPage from "./components/SearchPage.jsx";
import PreviewModal from "./components/PreviewModal.jsx";
import { useDocumentPreview } from "./hooks/useDocumentPreview.js";

export default function App() {
  const [tab, setTab] = useState("library");
  const [libraryView, setLibraryView] = useState("list");
  const [apiUp, setApiUp] = useState(null);
  const [docCount, setDocCount] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);
  const preview = useDocumentPreview();

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
          <span className="brand-mark" aria-hidden="true">P</span>
          <div className="brand-text">
            <span className="brand-name">Precedent Bank</span>
            <span className="brand-tag">MVP · The Lion's Pit 2026</span>
          </div>
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

            <div className="view-toggle">
              <button
                className={`view-toggle-btn ${libraryView === "list" ? "active" : ""}`}
                onClick={() => setLibraryView("list")}
              >
                List view
              </button>
              <button
                className={`view-toggle-btn ${libraryView === "lineage" ? "active" : ""}`}
                onClick={() => setLibraryView("lineage")}
              >
                Lineage graph
              </button>
            </div>

            {libraryView === "list" && (
              <DocumentLibrary refreshKey={refreshKey} onReset={bumpRefresh} onPreview={preview.openPreview} />
            )}
            {libraryView === "lineage" && (
              <LineageGraph refreshKey={refreshKey} onPreview={preview.openPreview} />
            )}
          </>
        )}

        {tab === "search" && <SearchPage onPreview={preview.openPreview} />}
      </main>

      <PreviewModal
        open={preview.open}
        doc={preview.doc}
        loading={preview.loading}
        error={preview.error}
        onClose={preview.closePreview}
      />
    </div>
  );
}
