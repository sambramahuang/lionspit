import { useEffect, useState } from "react";
import { api } from "../api.js";

// Shared by every place a document can be previewed (search results, the
// library table, the lineage graph) so there's one fetch/open/close
// implementation instead of one per screen.
export function useDocumentPreview() {
  const [doc, setDoc] = useState(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") closePreview();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const openPreview = async (docId) => {
    setOpen(true);
    setLoading(true);
    setDoc(null);
    setError(null);
    try {
      const res = await api.getDocument(docId);
      setDoc(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const closePreview = () => {
    setOpen(false);
    setDoc(null);
    setError(null);
  };

  return { doc, open, loading, error, openPreview, closePreview };
}
