import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import { supabase, supabaseConfigError } from "./supabaseClient.js";
import Auth from "./components/Auth.jsx";
import MattersView from "./components/MattersView.jsx";
import PageWipe from "./components/PageWipe.jsx";
import StartHereView from "./components/StartHereView.jsx";
import UploadPanel from "./components/UploadPanel.jsx";
import DocumentLibrary from "./components/DocumentLibrary.jsx";
import LineageGraph from "./components/LineageGraph.jsx";
import SearchPage from "./components/SearchPage.jsx";
import PreviewModal from "./components/PreviewModal.jsx";
import SlicedWaves from "./components/SlicedWaves/SlicedWaves.jsx";
import Dock from "./components/Dock/Dock.jsx";
import TiltedCard from "./components/TiltedCard/TiltedCard.jsx";
import { useDocumentPreview } from "./hooks/useDocumentPreview.js";

const prefersReducedMotion =
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

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

function StartHereIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M5 3v18" />
      <path d="M5 4h11l-2.5 4L16 12H5" />
    </svg>
  );
}

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

function MattersIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M12 3l8 4v5c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V7l8-4z" />
    </svg>
  );
}

const TAB_ITEMS = [
  { key: "start", label: "Start Here", icon: <StartHereIcon /> },
  { key: "library", label: "Library", icon: <LibraryIcon /> },
  { key: "search", label: "Search & Draft", icon: <SearchIcon /> },
  { key: "matters", label: "Matters", icon: <MattersIcon /> },
];

export default function App() {
  const [session, setSession] = useState(undefined); // undefined = checking, null = signed out
  const [me, setMe] = useState(null);
  const [tab, setTab] = useState("start");
  // What's actually rendered -- lags behind `tab` during a wipe so the
  // content swap happens while the panel fully covers the screen, not
  // visibly mid-transition. Equal to `tab` outside of a transition.
  const [displayedTab, setDisplayedTab] = useState("start");
  const [wipePhase, setWipePhase] = useState(null); // null | "covering" | "revealing"
  const [libraryView, setLibraryView] = useState("list");
  const [refreshKey, setRefreshKey] = useState(0);
  const [apiUp, setApiUp] = useState(null);
  const [docCount, setDocCount] = useState(0);
  const preview = useDocumentPreview();

  const bumpRefresh = () => setRefreshKey((k) => k + 1);

  const changeTab = (next) => {
    if (next === tab || wipePhase) return; // ignore repeats and mid-transition clicks
    setTab(next);
    if (prefersReducedMotion) {
      setDisplayedTab(next);
      return;
    }
    setWipePhase("covering");
  };

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: sub } = supabase.auth.onAuthStateChange((_event, sess) => setSession(sess));
    return () => sub.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!session) {
      setMe(null);
      return;
    }
    api.me().then(setMe).catch(() => setMe(null));
  }, [session]);

  useEffect(() => {
    if (!session) return;
    api.health()
      .then((res) => {
        setApiUp(true);
        setDocCount(res.documents_indexed);
      })
      .catch(() => setApiUp(false));
  }, [session, refreshKey]);

  if (supabaseConfigError) {
    return (
      <div className="app-shell" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
        <div className="card error-banner" style={{ maxWidth: 480 }}>{supabaseConfigError}</div>
      </div>
    );
  }

  if (session === undefined) return <p className="spinner-text">Loading...</p>;
  if (!session) return <Auth />;

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
          opacity={0.13}
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
        <div className="brand">
          <TiltedCard
            imageSrc="/kitsu-logo.png"
            altText="Kitsu AI"
            captionText="Kitsu AI"
            containerHeight="96px"
            containerWidth="96px"
            imageHeight="96px"
            imageWidth="96px"
            rotateAmplitude={14}
            scaleOnHover={1.08}
            showMobileWarning={false}
            showTooltip={false}
          />
        </div>

        <Dock
          items={TAB_ITEMS.map((t) => ({
            icon: t.icon,
            label: t.label,
            onClick: () => changeTab(t.key),
            className: tab === t.key ? "active" : "",
          }))}
          panelHeight={64}
          baseItemSize={56}
          magnification={80}
          distance={140}
        />

        <div className="status-pill" style={{ gap: 10 }}>
          <span className="mono" style={{ color: "var(--text-muted)" }}>{me?.email}</span>
          <button className="btn btn-ghost" onClick={() => supabase.auth.signOut()}>Sign out</button>
          <span className={`status-dot ${apiUp === false ? "down" : ""}`} />
          {apiUp === null && "checking..."}
          {apiUp === true && `${docCount} docs indexed`}
          {apiUp === false && "API offline"}
        </div>
      </header>

      <main className="content">
        {displayedTab === "start" && (
          <StartHereView onPreview={preview.openPreview} onGoToSearch={() => changeTab("search")} />
        )}

        {displayedTab === "library" && (
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
              <DocumentLibrary
                refreshKey={refreshKey}
                onChanged={bumpRefresh}
                onPreview={preview.openPreview}
                isPartner={!!me?.is_partner}
              />
            )}
            {libraryView === "lineage" && (
              <LineageGraph refreshKey={refreshKey} onPreview={preview.openPreview} />
            )}
          </>
        )}

        {displayedTab === "search" && <SearchPage onPreview={preview.openPreview} />}
        {displayedTab === "matters" && <MattersView isPartner={!!me?.is_partner} />}
      </main>

      {wipePhase && (
        <PageWipe
          phase={wipePhase}
          onCoverComplete={() => {
            setDisplayedTab(tab);
            setWipePhase("revealing");
          }}
          onRevealComplete={() => setWipePhase(null)}
        />
      )}

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
