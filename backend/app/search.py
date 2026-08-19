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
from datetime import datetime, timedelta

from app import matters, vectorstore
from app.llm_client import call_llm_json
from app.models import (
    ClauseAccessRestricted,
    ClauseResult,
    ClauseSearchResponse,
    DocumentMetadata,
    LineageCluster,
    LineageEdge,
    LineageNode,
    LineageResponse,
    RankingWeights,
    RejectedItem,
    SearchResponse,
    SearchResultItem,
)

RELEVANCE_SYSTEM_PROMPT = """You are a legal research assistant helping a lawyer find genuinely
useful precedent documents. You are given a search query and a list of candidate documents that
already passed a semantic-similarity and ranking-score filter. Some of them may be semantically
close in wording but not actually a useful precedent for this query -- e.g. right practice area but
the wrong kind of clause, or a document that only mentions related terms in passing. Judge each
candidate's real relevance to the query.

Respond with ONLY a single JSON object, no prose, no markdown fences, shaped as:

{
  "judgments": [
    {"doc_id": "...", "relevant": true or false, "reason": "one short plain-English sentence"}
  ]
}

Include exactly one judgment per candidate given. Always fill in "reason": if relevant, say briefly
why it's useful for this query; if not, say briefly why it falls short.
"""


def _build_relevance_block(c: dict) -> str:
    meta = c["meta"]
    return (
        f"doc_id: {c['doc_id']}\n"
        f"filename: {meta.get('filename')}\n"
        f"document_type: {meta.get('document_type')}\n"
        f"short_description: {meta.get('short_description')}\n"
        f"excerpt: {c['text'][:500]}"
    )


def _judge_relevance_with_llm(query: str, candidates: list) -> dict:
    """Asks the LLM to judge true relevance of each candidate to the query,
    beyond raw embedding similarity. Fails open (returns {}) on any LLM
    error so a flaky API call never breaks search -- results just fall
    back to the embedding + weighted-score ranking alone."""
    if not candidates:
        return {}
    blocks = "\n\n".join(_build_relevance_block(c) for c in candidates)
    user_prompt = f"Search query: {query}\n\nCandidates:\n\n{blocks}"
    try:
        data = call_llm_json(RELEVANCE_SYSTEM_PROMPT, user_prompt, max_tokens=800)
    except Exception:
        return {}
    out = {}
    for j in data.get("judgments", []):
        doc_id = j.get("doc_id")
        if doc_id:
            out[doc_id] = {
                "relevant": bool(j.get("relevant", True)),
                "reason": j.get("reason", ""),
            }
    return out


def _parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value[:10], fmt)
        except (ValueError, TypeError):
            continue
    return None


RECENCY_WINDOWS = {
    "30d": timedelta(days=30),
    "6m": timedelta(days=182),
    "1y": timedelta(days=365),
    "3y": timedelta(days=365 * 3),
    "5y": timedelta(days=365 * 5),
}


def _matches_recency(value: str | None, window: str | None) -> bool:
    if not window:
        return True
    document_date = _parse_date(value)
    age = RECENCY_WINDOWS.get(window)
    if not document_date or not age:
        return False
    now = datetime.now()
    return now - age <= document_date <= now


def _normalize(values: dict) -> dict:
    """Min-max normalize a {key: number} dict to 0..1. Flat input -> all 0.5."""
    if not values:
        return {}
    nums = list(values.values())
    lo, hi = min(nums), max(nums)
    if hi == lo:
        return {k: 0.5 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def run_search(req, user_email: str) -> SearchResponse:
    raw = vectorstore.query(req.query, n_results=max(req.candidate_pool, 12))
    ids = raw["ids"][0]
    docs = raw["documents"][0]
    metas = raw["metadatas"][0]
    distances = raw["distances"][0]

    candidates = []
    for doc_id, text, meta, dist in zip(ids, docs, metas, distances):
        similarity = max(0.0, min(1.0, 1 - dist))
        candidates.append(
            {
                "doc_id": doc_id,
                "text": text,
                "meta": meta,
                "similarity": similarity,
            }
        )

    # --- Step 1: matter-level ethical wall ------------------------------
    walls = matters.load_walls()
    access_restricted = []
    visible = []
    for c in candidates:
        if matters.is_blocked(c["meta"], user_email, walls):
            access_restricted.append(
                RejectedItem(
                    doc_id=c["doc_id"],
                    filename=c["meta"].get("filename", c["doc_id"]),
                    metadata=DocumentMetadata(**c["meta"]),
                    reason="This matter is walled off. You don't have access to view it.",
                )
            )
        else:
            visible.append(c)

    # --- Step 2: optional hard filters (jurisdiction / matter type) ----
    if req.jurisdiction_filter:
        visible = [
            c
            for c in visible
            if req.jurisdiction_filter.lower()
            in str(c["meta"].get("jurisdiction", "")).lower()
        ] or visible
    if req.matter_type_filter:
        visible = [
            c
            for c in visible
            if req.matter_type_filter.lower()
            in str(c["meta"].get("matter_type", "")).lower()
        ] or visible
    if req.recency_filter:
        visible = [
            c
            for c in visible
            if _matches_recency(c["meta"].get("document_date"), req.recency_filter)
        ]
    if req.status_filters:
        visible = [c for c in visible if c["meta"].get("status") in req.status_filters]
    if req.document_type_filters:
        visible = [
            c
            for c in visible
            if c["meta"].get("document_type") in req.document_type_filters
        ]

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
            jurisdiction_score = (
                1.0
                if req.jurisdiction_filter.lower()
                in str(meta.get("jurisdiction", "")).lower()
                else 0.0
            )
        else:
            jurisdiction_score = 0.5  # neutral when no filter is applied

        breakdown = {
            "similarity": round(c["similarity"], 3),
            "recency": round(recency_norm.get(c["doc_id"], 0.5), 3),
            "frequency": round(freq_norm.get(c["doc_id"], 0.0), 3),
            "partner_approval": partner_score,
            "jurisdiction_match": jurisdiction_score,
        }
        total_weight = (
            w.similarity
            + w.recency
            + w.frequency
            + w.partner_approval
            + w.jurisdiction_match
        ) or 1.0
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
        clusters[matters.cluster_key(c["meta"])].append(c)

    rejected_ids = set()
    rejected_items = []
    for key, group in clusters.items():
        if len(group) < 2:
            continue
        # best-in-cluster = highest score, wins as the "current" version
        group_sorted = sorted(group, key=lambda c: c["score"], reverse=True)
        best = group_sorted[0]
        for other in group_sorted[1:]:
            reasons = []
            best_date = _parse_date(best["meta"].get("document_date"))
            other_date = _parse_date(other["meta"].get("document_date"))
            if best_date and other_date and other_date < best_date:
                reasons.append(
                    f"superseded by a later version dated {best['meta'].get('document_date')}"
                )
            if (
                best["meta"].get("partner_approved") is True
                and other["meta"].get("partner_approved") is not True
            ):
                reasons.append(
                    "not partner-approved, while a partner-approved version of this matter exists"
                )
            if (
                other["meta"].get("version")
                and best["meta"].get("version")
                and str(other["meta"].get("version")) < str(best["meta"].get("version"))
            ):
                reasons.append(
                    f"lower version ({other['meta'].get('version')}) than the current one ({best['meta'].get('version')})"
                )

            if reasons:
                rejected_ids.add(other["doc_id"])
                rejected_items.append(
                    RejectedItem(
                        doc_id=other["doc_id"],
                        filename=other["meta"].get("filename", other["doc_id"]),
                        metadata=DocumentMetadata(**other["meta"]),
                        reason="Rejected: " + "; ".join(reasons) + ".",
                    )
                )

    remaining = [c for c in visible if c["doc_id"] not in rejected_ids]

    # --- Step 5: LLM relevance judgment -----------------------------------
    # Embedding similarity + the weighted score can surface documents that
    # are semantically close in wording but not actually useful precedents
    # for this query. Have the LLM review the surviving pool, drop anything
    # it judges not genuinely relevant (moved into "rejected" with a plain
    # -English reason), and attach a reason to what it keeps.
    judgments = _judge_relevance_with_llm(req.query, remaining)
    if judgments:
        still_relevant = []
        for c in remaining:
            j = judgments.get(c["doc_id"])
            if j is None:
                still_relevant.append(
                    c
                )  # no judgment returned for this one -- fail open, keep it
                continue
            c["llm_relevance_reason"] = j["reason"]
            if j["relevant"]:
                still_relevant.append(c)
            else:
                rejected_ids.add(c["doc_id"])
                rejected_items.append(
                    RejectedItem(
                        doc_id=c["doc_id"],
                        filename=c["meta"].get("filename", c["doc_id"]),
                        metadata=DocumentMetadata(**c["meta"]),
                        reason="Not relevant to this query: "
                        + (j["reason"] or "judged not relevant."),
                    )
                )
        remaining = still_relevant

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
            llm_relevance_reason=c.get("llm_relevance_reason"),
        )

    return SearchResponse(
        query=req.query,
        candidates_considered=len(candidates),
        kept=[to_result_item(c) for c in kept_raw],
        other_candidates=[to_result_item(c) for c in other_raw],
        rejected=rejected_items,
        access_restricted=access_restricted,
    )


def run_clause_search(req, user_email: str) -> ClauseSearchResponse:
    """Clause-level counterpart to run_search: instead of ranking whole
    documents, ranks individual clauses (see ingestion.split_into_clauses)
    so a lawyer can find "the indemnity cap" directly instead of a
    document that merely mentions indemnity somewhere in 12 pages.

    No LLM relevance pass here, unlike run_search: a clause is already a
    narrow, specific unit of text (not a whole document that might
    mention a topic only in passing), so raw embedding similarity is a
    much more reliable relevance signal at this granularity, and skipping
    the extra LLM call keeps clause search fast."""
    candidates = vectorstore.query_clauses(
        req.query, n_results=max(req.candidate_pool, 1)
    )

    walls = matters.load_walls()
    visible, access_restricted = [], []
    for c in candidates:
        if matters.is_blocked(c["meta"], user_email, walls):
            access_restricted.append(
                ClauseAccessRestricted(
                    doc_id=c["doc_id"],
                    filename=c["meta"].get("filename", c["doc_id"]),
                    reason="This matter is walled off. You don't have access to view it.",
                )
            )
        else:
            visible.append(c)

    visible.sort(key=lambda c: c["similarity"], reverse=True)
    keep_n = max(req.keep_top, 0)
    kept = [
        ClauseResult(
            doc_id=c["doc_id"],
            filename=c["meta"].get("filename", c["doc_id"]),
            clause_index=c["clause_index"],
            label=c["label"],
            text=c["text"],
            similarity=round(c["similarity"], 3),
            metadata=DocumentMetadata(**c["meta"]),
        )
        for c in visible[:keep_n]
    ]

    return ClauseSearchResponse(
        query=req.query,
        candidates_considered=len(candidates),
        kept=kept,
        access_restricted=access_restricted,
    )


def _to_lineage_node(record: dict) -> LineageNode:
    meta = record["metadata"]
    return LineageNode(
        doc_id=record["doc_id"],
        filename=meta.get("filename", record["doc_id"]),
        metadata=DocumentMetadata(**meta),
    )


def _supersession_reason(current_meta: dict, other_meta: dict) -> str:
    """Same comparison rules run_search uses to reject a superseded doc
    against the best-in-cluster -- reused here so supersession is explained
    the same way in search results and in the lineage graph."""
    reasons = []
    current_date = _parse_date(current_meta.get("document_date"))
    other_date = _parse_date(other_meta.get("document_date"))
    if current_date and other_date and other_date < current_date:
        reasons.append(
            f"superseded by a later version dated {current_meta.get('document_date')}"
        )
    if (
        current_meta.get("partner_approved") is True
        and other_meta.get("partner_approved") is not True
    ):
        reasons.append("not partner-approved, while a partner-approved version exists")
    if (
        other_meta.get("version")
        and current_meta.get("version")
        and str(other_meta.get("version")) < str(current_meta.get("version"))
    ):
        reasons.append(
            f"lower version ({other_meta.get('version')}) than the current one ({current_meta.get('version')})"
        )
    return "; ".join(reasons) if reasons else "earlier document in the same matter"


def compute_lineage(user_email: str) -> LineageResponse:
    """Corpus-wide view of the same matter-clustering + supersession logic
    run_search uses per-query, exposed as a standalone graph: one cluster
    per matter (matter_type + practice_area + jurisdiction), with the
    "current" document at the hub and every other version pointing to it
    with a plain-English reason. Documents with no cluster-mate are listed
    separately rather than force-fit into a graph with nothing to show.

    Walled matters are excluded entirely before clustering starts, same as
    run_search's access_restricted step, so a walled matter's documents
    never surface in this view for someone outside its allow-list."""
    walls = matters.load_walls()
    records = [
        r
        for r in vectorstore.list_all()
        if not matters.is_blocked(r["metadata"], user_email, walls)
    ]

    grouped = defaultdict(list)
    for r in records:
        grouped[matters.cluster_key(r["metadata"])].append(r)

    clusters = []
    standalone = []
    for key, group in grouped.items():
        if len(group) < 2:
            standalone.extend(_to_lineage_node(r) for r in group)
            continue

        def sort_key(r):
            meta = r["metadata"]
            d = _parse_date(meta.get("document_date"))
            return (
                1 if meta.get("partner_approved") is True else 0,
                d.timestamp() if d else 0,
                str(meta.get("version") or ""),
            )

        group_sorted = sorted(group, key=sort_key, reverse=True)
        current = group_sorted[0]
        others = group_sorted[1:]

        edges = [
            LineageEdge(
                from_doc_id=other["doc_id"],
                to_doc_id=current["doc_id"],
                reason=_supersession_reason(current["metadata"], other["metadata"]),
            )
            for other in others
        ]

        client = current["metadata"].get("client_name") or "Unnamed client"
        matter = current["metadata"].get("matter_type") or "Matter"
        jurisdiction = current["metadata"].get("jurisdiction")
        label = f"{client} — {matter} · {jurisdiction}" if jurisdiction else f"{client} — {matter}"
        # Same reasoning as matters.summarize()'s label: show the explicit
        # reference number actually driving cluster_key's grouping, not just
        # the current document's own (possibly type-specific) matter_type.
        reference = next((r["metadata"].get("matter_reference") for r in group_sorted if r["metadata"].get("matter_reference")), None)
        if reference:
            label = f"{reference} — {label}"

        clusters.append(
            LineageCluster(
                key=key,
                label=label,
                current_doc_id=current["doc_id"],
                nodes=[_to_lineage_node(r) for r in group_sorted],
                edges=edges,
            )
        )

    clusters.sort(key=lambda c: len(c.nodes), reverse=True)
    return LineageResponse(clusters=clusters, standalone=standalone)
