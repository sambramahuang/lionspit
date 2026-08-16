import React, { useState } from "react";
import UploadPanel from "./components/UploadPanel.jsx";
import DocumentLibrary from "./components/DocumentLibrary.jsx";
import LineageGraph from "./components/LineageGraph.jsx";
import SearchPage from "./components/SearchPage.jsx";
import PreviewModal from "./components/PreviewModal.jsx";
import SlicedWaves from "./components/SlicedWaves/SlicedWaves.jsx";
import Dock from "./components/Dock/Dock.jsx";
import { useDocumentPreview } from "./hooks/useDocumentPreview.js";

const ICON_PROPS = {
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

function LibraryIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg {...ICON_PROPS}>
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </svg>
  );
}

const TAB_ITEMS = [
  { key: "library", label: "Library", icon: <LibraryIcon /> },
  { key: "search", label: "Search & Draft", icon: <SearchIcon /> },
];

export default function App() {
  const [tab, setTab] = useState("library");
  const [libraryView, setLibraryView] = useState("list");
  const [refreshKey, setRefreshKey] = useState(0);
  const preview = useDocumentPreview();

  const bumpRefresh = () => setRefreshKey((k) => k + 1);

  return (
    <div className="app-shell">
      <div className="app-bg">
        <SlicedWaves
          color1="#c79a55"
          color2="#1b2430"
          color3="#a9752f"
          columns={14}
          rows={8}
          barThickness={0.08}
          speed={0.25}
          travel={0.7}
          waveSpread={0.9}
          rowOffset={1.0}
          softness={0.12}
          glow={0}
          brightness={1.0}
          contrast={1.0}
          opacity={0.22}
          orientation="horizontal"
          alternate={false}
          mouseInteraction={true}
          mouseStrength={1}
          mouseRadius={0.3}
          grain={true}
          grainIntensity={0.05}
        />
      </div>

      <header className="topbar">
        <Dock
          items={TAB_ITEMS.map((t) => ({
            icon: t.icon,
            label: t.label,
            onClick: () => setTab(t.key),
            className: tab === t.key ? "active" : "",
          }))}
          panelHeight={64}
          baseItemSize={56}
          magnification={80}
          distance={140}
        />
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
