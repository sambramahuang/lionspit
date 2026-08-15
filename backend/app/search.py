"""
Search + ranking + rejection reasoning.

Flow (mirrors the demo script):
  1. Pull a candidate pool via semantic search (Chroma).
  2. Split off anything the viewer isn't cleared to see (ethical wall).
  3. Score the rest on similarity + recency + frequency + partner
     approval + jurisdiction match.
  4. Detect same-matter clusters and flag clearly superseded / non
     -approved documents as "rejected", with a plain-English reason.
  5. Whatever's left, ranked, becomes "kept" (top N) and
     "other_candidates" (the rest) -- both filterable/comparable in the UI.
"""
from collections import defaultdict
from datetime import datetime

from app import vectorstore
from app.models import (
    DocumentMetadata,
    RankingWeights,
    RejectedItem,
    SearchResponse,
    SearchResultItem,
)


def _parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value[:10], fmt)
        except (ValueError, TypeError):
            continue
    return None


def _normalize(values: dict) -> dict:
    """Min-max normalize a {key: number} dict to 0..1. Flat input -> all 0.5."""
    if not values:
        return {}
    nums = list(values.values())
    lo, hi = min(nums), max(nums)
    if hi == lo:
        return {k: 0.5 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def _cluster_key(meta: dict) -> str:
    """Rough same-matter grouping so we can compare versions against each
    other rather than against the whole corpus. Good enough for a
    hackathon-scale corpus; a production system would use a real matter ID."""
    return "|".join([
        str(meta.get("matter_type", "")).lower().strip(),
        str(meta.get("practice_area", "")).lower().strip(),
        str(meta.get("jurisdiction", "")).lower().strip(),
    ])


def run_search(req) -> SearchResponse:
    raw = vectorstore.query(req.query, n_results=max(req.candidate_pool, 12))
    ids = raw["ids"][0]
    docs = raw["documents"][0]
    metas = raw["metadatas"][0]
    distances = raw["distances"][0]

    candidates = []
    for doc_id, text, meta, dist in zip(ids, docs, metas, distances):
        similarity = max(0.0, min(1.0, 1 - dist))
        candidates.append({
            "doc_id": doc_id,
            "text": text,
            "meta": meta,
            "similarity": similarity,
        })

    # --- Step 1: ethical wall / confidentiality filter -----------------
    access_restricted = []
    visible = []
    for c in candidates:
        if c["meta"].get("confidentiality") == "restricted" and req.viewer_clearance != "elevated":
            access_restricted.append(RejectedItem(
                doc_id=c["doc_id"],
                filename=c["meta"].get("filename", c["doc_id"]),
                metadata=DocumentMetadata(**c["meta"]),
                reason="Restricted document. Requires elevated access clearance to view.",
            ))
        else:
            visible.append(c)

    # --- Step 2: optional hard filters (jurisdiction / matter type) ----
    if req.jurisdiction_filter:
        visible = [c for c in visible
                   if req.jurisdiction_filter.lower() in str(c["meta"].get("jurisdiction", "")).lower()] or visible
    if req.matter_type_filter:
        visible = [c for c in visible
                   if req.matter_type_filter.lower() in str(c["meta"].get("matter_type", "")).lower()] or visible

    visible = visible[: max(req.candidate_pool, 1)]

    # --- Step 3: composite ranking score --------------------------------
    recency_raw, freq_raw = {}, {}
    for c in visible:
        d = _parse_date(c["meta"].get("document_date"))
        recency_raw[c["doc_id"]] = d.timestamp() if d else 0
        freq_raw[c["doc_id"]] = float(c["meta"].get("usage_count", 0) or 0)

    recency_norm = _normalize(recency_raw)
    freq_norm = _normalize(freq_raw)
    w: RankingWeights = req.weights

    for c in visible:
        meta = c["meta"]
        partner_score = 1.0 if meta.get("partner_approved") is True else 0.0
        if req.jurisdiction_filter:
            jurisdiction_score = 1.0 if req.jurisdiction_filter.lower() in str(meta.get("jurisdiction", "")).lower() else 0.0
        else:
            jurisdiction_score = 0.5  # neutral when no filter is applied

        breakdown = {
            "similarity": round(c["similarity"], 3),
            "recency": round(recency_norm.get(c["doc_id"], 0.5), 3),
            "frequency": round(freq_norm.get(c["doc_id"], 0.0), 3),
            "partner_approval": partner_score,
            "jurisdiction_match": jurisdiction_score,
        }
        total_weight = (w.similarity + w.recency + w.frequency + w.partner_approval + w.jurisdiction_match) or 1.0
        score = (
            breakdown["similarity"] * w.similarity
            + breakdown["recency"] * w.recency
            + breakdown["frequency"] * w.frequency
            + breakdown["partner_approval"] * w.partner_approval
            + breakdown["jurisdiction_match"] * w.jurisdiction_match
        ) / total_weight
        c["score"] = round(score, 4)
        c["breakdown"] = breakdown

    visible.sort(key=lambda c: c["score"], reverse=True)

    # --- Step 4: detect clearly superseded / non-approved documents ----
    clusters = defaultdict(list)
    for c in visible:
        clusters[_cluster_key(c["meta"])].append(c)

    rejected_ids = set()
    rejected_items = []
    for key, group in clusters.items():
        if len(group) < 2 or key == "||":
            continue
        # best-in-cluster = highest score, wins as the "current" version
        group_sorted = sorted(group, key=lambda c: c["score"], reverse=True)
        best = group_sorted[0]
        for other in group_sorted[1:]:
            reasons = []
            best_date = _parse_date(best["meta"].get("document_date"))
            other_date = _parse_date(other["meta"].get("document_date"))
            if best_date and other_date and other_date < best_date:
                reasons.append(f"superseded by a later version dated {best['meta'].get('document_date')}")
            if best["meta"].get("partner_approved") is True and other["meta"].get("partner_approved") is not True:
                reasons.append("not partner-approved, while a partner-approved version of this matter exists")
            if other["meta"].get("version") and best["meta"].get("version") and \
               str(other["meta"].get("version")) < str(best["meta"].get("version")):
                reasons.append(f"lower version ({other['meta'].get('version')}) than the current one ({best['meta'].get('version')})")

            if reasons:
                rejected_ids.add(other["doc_id"])
                rejected_items.append(RejectedItem(
                    doc_id=other["doc_id"],
                    filename=other["meta"].get("filename", other["doc_id"]),
                    metadata=DocumentMetadata(**other["meta"]),
                    reason="Rejected: " + "; ".join(reasons) + ".",
                ))

    remaining = [c for c in visible if c["doc_id"] not in rejected_ids]
    keep_n = max(req.keep_top, 0)
    kept_raw, other_raw = remaining[:keep_n], remaining[keep_n:]

    def to_result_item(c):
        return SearchResultItem(
            doc_id=c["doc_id"],
            filename=c["meta"].get("filename", c["doc_id"]),
            metadata=DocumentMetadata(**c["meta"]),
            score=c["score"],
            score_breakdown=c["breakdown"],
            similarity=round(c["similarity"], 3),
        )

    return SearchResponse(
        query=req.query,
        candidates_considered=len(candidates),
        kept=[to_result_item(c) for c in kept_raw],
        other_candidates=[to_result_item(c) for c in other_raw],
        rejected=rejected_items,
        access_restricted=access_restricted,
    )
