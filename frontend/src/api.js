const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: options.body instanceof FormData
      ? options.headers
      : { "Content-Type": "application/json", ...options.headers },
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

  listDocuments: () => request("/api/documents"),

  getDocument: (docId) => request(`/api/documents/${encodeURIComponent(docId)}`),

  resetDocuments: () => request("/api/documents", { method: "DELETE" }),

  ingest: (files) => {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    return request("/api/ingest", { method: "POST", body: form });
  },

  search: (payload) =>
    request("/api/search", { method: "POST", body: JSON.stringify(payload) }),

  draft: (payload) =>
    request("/api/draft", { method: "POST", body: JSON.stringify(payload) }),
};
