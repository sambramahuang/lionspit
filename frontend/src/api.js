import { supabase } from "./supabaseClient.js";

// Local dev runs the backend as a separate process on :8000. In production
// (Vercel Services), frontend and backend share one domain via rewrites, so
// API calls should stay relative -- an absolute localhost URL would try to
// reach the visitor's own machine. VITE_API_BASE_URL still overrides either
// way if set (checked with ?? so an explicit "" is respected, not skipped).
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

async function request(path, options = {}) {
  const { data: { session } } = await supabase.auth.getSession();
  const authHeader = session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {};

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: options.body instanceof FormData
      ? { ...authHeader, ...options.headers }
      : { "Content-Type": "application/json", ...authHeader, ...options.headers },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      // ignore
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json();
}

export const api = {
  health: () => request("/api/health"),

  me: () => request("/api/me"),

  listDocuments: () => request("/api/documents"),

  getDocument: (docId) => request(`/api/documents/${encodeURIComponent(docId)}`),

  resetDocuments: () => request("/api/documents", { method: "DELETE" }),

  deleteDocument: (docId) => request(`/api/documents/${encodeURIComponent(docId)}`, { method: "DELETE" }),

  setDocumentApproval: (docId, approved, note = null) =>
    request(`/api/documents/${encodeURIComponent(docId)}/approval`, {
      method: "POST",
      body: JSON.stringify({ approved, note }),
    }),

  lineage: () => request("/api/lineage"),

  listMatters: () => request("/api/matters"),

  setMatterWall: (matterKey, payload) =>
    request(`/api/matters/${encodeURIComponent(matterKey)}/wall`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  acknowledgeConflict: (matterKey) =>
    request(`/api/matters/${encodeURIComponent(matterKey)}/conflict/acknowledge`, { method: "POST" }),

  ingest: (files) => {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    return request("/api/ingest", { method: "POST", body: form });
  },

  // Extracts a file's text for use as one-off search context -- does NOT
  // add it to the library (unlike ingest above).
  extractText: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/api/extract-text", { method: "POST", body: form });
  },

  search: (payload) =>
    request("/api/search", { method: "POST", body: JSON.stringify(payload) }),

  searchClauses: (payload) =>
    request("/api/search/clauses", { method: "POST", body: JSON.stringify(payload) }),

  draft: (payload) =>
    request("/api/draft", { method: "POST", body: JSON.stringify(payload) }),
};
