import React, { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { supabase, supabaseConfigError } from "./supabaseClient.js";
import Auth from "./components/Auth.jsx";
import MattersView from "./components/MattersView.jsx";
import PageWipe from "./components/PageWipe.jsx";
import HeroView from "./components/HeroView.jsx";
import OverviewView from "./components/OverviewView.jsx";
import UploadPanel from "./components/UploadPanel.jsx";
import DocumentLibrary from "./components/DocumentLibrary.jsx";
import LineageGraph from "./components/LineageGraph.jsx";
import SearchPage from "./components/SearchPage.jsx";
import PreviewModal from "./components/PreviewModal.jsx";
import AppBackground from "./components/AppBackground.jsx";
import Dock from "./components/Dock/Dock.jsx";
import { useDocumentPreview } from "./hooks/useDocumentPreview.js";

const prefersReducedMotion =
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

const ICON_PROPS = {
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.9,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

function HomeIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M3 11.5 12 4l9 7.5" />
      <path d="M5.5 10v9h13v-9" />
      <path d="M9.5 19v-5h5v5" />
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

const TAB_ITEMS = [
  { key: "home", label: "Home", icon: <HomeIcon /> },
  { key: "library", label: "Library", icon: <LibraryIcon /> },
  { key: "search", label: "Search & Draft", icon: <SearchIcon /> },
];

const SAVED_VIEW_KEY = "kitsu:last-view";
const VALID_VIEWS = new Set(["welcome", "home", "library", "search"]);
const VALID_LIBRARY_VIEWS = new Set(["list", "lineage", "matters"]);

function readSavedView() {
  if (typeof window === "undefined") return { view: "home", libraryView: "list" };
  try {
    const saved = JSON.parse(window.localStorage.getItem(SAVED_VIEW_KEY) || "null");
    const view = VALID_VIEWS.has(saved?.view) ? saved.view : "home";
    return {
      view,
      libraryView: VALID_LIBRARY_VIEWS.has(saved?.libraryView) ? saved.libraryView : "list",
    };
  } catch {
    return { view: "home", libraryView: "list" };
  }
}

export default function App() {
  const savedView = readSavedView();
  const [session, setSession] = useState(undefined); // undefined = checking, null = signed out
  const [me, setMe] = useState(null);
  const [tab, setTab] = useState(savedView.view === "welcome" ? "home" : savedView.view);
  // What's actually rendered -- lags behind `tab` during a wipe so the
  // content swap happens while the panel fully covers the screen, not
  // visibly mid-transition. Equal to `tab` outside of a transition.
  const [displayedTab, setDisplayedTab] = useState(savedView.view);
  const [wipePhase, setWipePhase] = useState(null); // null | "covering" | "revealing"
  const [wipeDirection, setWipeDirection] = useState("right");
  const pendingViewRef = useRef(savedView.view);
  const [libraryView, setLibraryView] = useState(savedView.libraryView);
  const [refreshKey, setRefreshKey] = useState(0);
  const [apiUp, setApiUp] = useState(null);
  const [docCount, setDocCount] = useState(0);
  const preview = useDocumentPreview();

  // Same lag-behind-the-source-of-truth pattern as displayedTab/wipePhase
  // above, applied to the Auth -> app-shell boundary: displayedAuthed only
  // flips once the wipe has fully covered the screen, so the swap from the
  // login card to the dashboard happens hidden underneath the sweep instead
  // of as a jarring instant cut. wasAuthedRef (not state) tracks whether we
  // were already signed in, so a token refresh or an already-authenticated
  // page reload doesn't replay the entrance animation -- only an actual
  // sign-in transition (false -> true) does.
  const [displayedAuthed, setDisplayedAuthed] = useState(false);
  const [authWipePhase, setAuthWipePhase] = useState(null); // null | "covering" | "revealing"
  const wasAuthedRef = useRef(false);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        SAVED_VIEW_KEY,
        JSON.stringify({ view: displayedTab, libraryView })
      );
    } catch {
      // Storage can be unavailable in private browsing; navigation still works.
    }
  }, [displayedTab, libraryView]);

  const bumpRefresh = () => setRefreshKey((k) => k + 1);

  const changeTab = (next) => {
    if ((next === tab && displayedTab === next) || wipePhase) return; // ignore repeats and mid-transition clicks
    const currentIndex = TAB_ITEMS.findIndex((item) => item.key === tab);
    const nextIndex = TAB_ITEMS.findIndex((item) => item.key === next);
    pendingViewRef.current = next;
    setWipeDirection(nextIndex > currentIndex ? "right" : "left");
    setTab(next);
    if (prefersReducedMotion) {
      setDisplayedTab(next);
      return;
    }
    setWipePhase("covering");
  };

  const showWelcome = () => {
    if (wipePhase || (tab === "home" && displayedTab === "welcome")) return;
    const currentIndex = TAB_ITEMS.findIndex((item) => item.key === tab);
    pendingViewRef.current = "welcome";
    setWipeDirection(currentIndex === 0 ? "left" : "right");
    setTab("home");
    if (prefersReducedMotion) {
      setDisplayedTab("welcome");
      return;
    }
    setWipePhase("covering");
  };

  useEffect(() => {
    const applySession = (sess) => {
      setSession(sess);
      const authed = !!sess;
      if (authed && !wasAuthedRef.current) {
        pendingViewRef.current = "welcome";
        setTab("home");
        if (prefersReducedMotion) {
          setDisplayedTab("welcome");
          setDisplayedAuthed(true);
        } else {
          setAuthWipePhase("covering");
        }
      } else if (!authed) {
        setDisplayedAuthed(false);
        setAuthWipePhase(null);
      }
      wasAuthedRef.current = authed;
    };
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setDisplayedAuthed(!!data.session); // no animation for an already-authenticated page load
      wasAuthedRef.current = !!data.session;
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, sess) => applySession(sess));
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

  if (!displayedAuthed) {
    return (
      <>
        <Auth />
        {authWipePhase && (
          <PageWipe
            phase={authWipePhase}
            axis="y"
            direction="down"
            onCoverComplete={() => {
              setDisplayedTab(pendingViewRef.current);
              setDisplayedAuthed(true);
              setAuthWipePhase("revealing");
            }}
            onRevealComplete={() => setAuthWipePhase(null)}
          />
        )}
      </>
    );
  }

  const activeNavKey = displayedTab === "welcome" ? "home" : displayedTab;

  return (
    <div className="app-shell">
      {authWipePhase === "revealing" && (
        <PageWipe
          phase="revealing"
          axis="y"
          direction="down"
          onRevealComplete={() => setAuthWipePhase(null)}
        />
      )}
      <div className="app-bg">
        <AppBackground />
      </div>

      <header className="topbar">
        <div className="brand">
          <button className="brand-wordmark" onClick={showWelcome} type="button">
            Kitsu
          </button>
        </div>

        <Dock
          items={TAB_ITEMS.map((t) => ({
            icon: t.icon,
            label: t.label,
            onClick: () => changeTab(t.key),
            className: activeNavKey === t.key ? "active" : "",
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
        {displayedTab === "welcome" && <HeroView onExplore={() => changeTab("home")} />}

        {displayedTab === "home" && (
          <OverviewView
            onPreview={preview.openPreview}
            onGoToLibrary={() => changeTab("library")}
            onGoToSearch={() => changeTab("search")}
          />
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
              <button
                className={`view-toggle-btn ${libraryView === "matters" ? "active" : ""}`}
                onClick={() => setLibraryView("matters")}
              >
                Matters
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
              <LineageGraph
                refreshKey={refreshKey}
                onPreview={preview.openPreview}
                isPartner={!!me?.is_partner}
                onChanged={bumpRefresh}
              />
            )}
            {libraryView === "matters" && (
              <MattersView refreshKey={refreshKey} isPartner={!!me?.is_partner} onChanged={bumpRefresh} />
            )}
          </>
        )}

        {displayedTab === "search" && <SearchPage onPreview={preview.openPreview} />}
      </main>

      {wipePhase && (
        <PageWipe
          phase={wipePhase}
          direction={wipeDirection}
          onCoverComplete={() => {
            setDisplayedTab(pendingViewRef.current);
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
