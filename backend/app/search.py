"""
Search + ranking + rejection reasoning.

Flow (mirrors the demo script):
  1. Pull a candidate pool via semantic search (Chroma), then split off
     anything the viewer isn't cleared to see (ethical wall) -- scored
     alongside the visible pool (step 3) but not yet disclosed.
  2. Apply hard filters (jurisdiction/matter type/recency/status/document
     type) to both pools identically.
  3. Score the visible pool on similarity + recency + frequency + partner
     approval + jurisdiction match; score the walled pool the same way, on
     the same scale, without it skewing the visible pool's own scoring.
  4. Detect same-matter clusters and flag clearly superseded / non
     -approved documents as "rejected", with a plain-English reason.
  5. Have the LLM judge true relevance on what's left; drop anything it
     judges not genuinely relevant into "rejected" too.
  6. Whatever survives becomes "kept" (anything scoring within a
     threshold of the top result, capped) and "other_candidates" (the
     rest) -- both filterable/comparable in the UI. A walled candidate
     only surfaces as "access restricted" if it clears that same
     threshold -- genuinely relevant, not just incidentally similar.
"""

from collections import defaultdict
from datetime import datetime, timedelta
import re

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


# How close to the top-scoring result a candidate must be to count as
# "kept" (see run_search's Step 6) -- 0.8 means anything scoring within 20%
# of the best match qualifies. Relative rather than an absolute cutoff
# because `score` is a weighted composite (Step 3) that shifts with the
# caller's ranking weights, so a fixed number would drift in meaning as
# those weights change.
RELATIVE_KEEP_THRESHOLD = 0.8

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


def _normalize_against(value: float, reference: list) -> float:
    """Same min-max formula as _normalize, but scored against someone
    else's reference range instead of its own -- used to score a walled
    candidate on the same 0..1 scale as the visible pool without letting
    it skew the visible pool's own normalization (see its call site)."""
    if not reference:
        return 0.5
    lo, hi = min(reference), max(reference)
    if hi == lo:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def _weighted_score(breakdown: dict, w: RankingWeights) -> float:
    """The composite-score formula, factored out so it's computed exactly
    the same way for a visible candidate (Step 3) and a walled one (Step
    1b) -- the whole point of scoring walled candidates at all is to hold
    them to the identical bar, not an approximation of it."""
    total_weight = (
        w.similarity + w.recency + w.frequency + w.partner_approval + w.jurisdiction_match
    ) or 1.0
    return (
        breakdown["similarity"] * w.similarity
        + breakdown["recency"] * w.recency
        + breakdown["frequency"] * w.frequency
        + breakdown["partner_approval"] * w.partner_approval
        + breakdown["jurisdiction_match"] * w.jurisdiction_match
    ) / total_weight


def _apply_hard_filters(pool: list, req) -> list:
    """Jurisdiction/matter-type filters are soft (fall back to unfiltered
    if they'd eliminate everything -- `or pool`); recency/status/document
    -type filters are hard. Factored out so a walled candidate is judged
    against the exact same filters a visible one is, not a re-typed
    approximation of them (see run_search's two call sites)."""
    if req.jurisdiction_filter:
        pool = [
            c for c in pool
            if req.jurisdiction_filter.lower() in str(c["meta"].get("jurisdiction", "")).lower()
        ] or pool
    if req.matter_type_filter:
        pool = [
            c for c in pool
            if req.matter_type_filter.lower() in str(c["meta"].get("matter_type", "")).lower()
        ] or pool
    if req.recency_filter:
        pool = [c for c in pool if _matches_recency(c["meta"].get("document_date"), req.recency_filter)]
    if req.is_draft_or_model_filters:
        pool = [c for c in pool if c["meta"].get("is_draft_or_model") in req.is_draft_or_model_filters]
    if req.document_type_filters:
        pool = [c for c in pool if c["meta"].get("document_type") in req.document_type_filters]
    return pool


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
    # Walled candidates aren't decided here -- only split out. Whether one
    # is worth disclosing at all (see Step 3b) needs its score, which isn't
    # computed until Step 3, and needs to be judged on the same scale as
    # the visible pool.
    walls = matters.load_walls()
    blocked, visible = [], []
    for c in candidates:
        (blocked if matters.is_blocked(c["meta"], user_email, walls) else visible).append(c)

    # --- Step 2: optional hard filters (jurisdiction / matter type) ----
    # Applied to both pools identically -- a walled candidate that doesn't
    # even match the stated jurisdiction/date/type filters has no more
    # business surfacing than a visible one that fails the same filters.
    visible = _apply_hard_filters(visible, req)
    blocked = _apply_hard_filters(blocked, req)

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

    def _jurisdiction_score(meta: dict) -> float:
        if not req.jurisdiction_filter:
            return 0.5  # neutral when no filter is applied
        return (
            1.0
            if req.jurisdiction_filter.lower() in str(meta.get("jurisdiction", "")).lower()
            else 0.0
        )

    for c in visible:
        meta = c["meta"]
        breakdown = {
            "similarity": round(c["similarity"], 3),
            "recency": round(recency_norm.get(c["doc_id"], 0.5), 3),
            "frequency": round(freq_norm.get(c["doc_id"], 0.0), 3),
            "partner_approval": 1.0 if meta.get("partner_approved") is True else 0.0,
            "jurisdiction_match": _jurisdiction_score(meta),
        }
        c["score"] = round(_weighted_score(breakdown, w), 4)
        c["breakdown"] = breakdown

    visible.sort(key=lambda c: c["score"], reverse=True)

    # --- Step 3b: score walled candidates on the same scale -------------
    # Scored (never shown) against the visible pool's own recency/frequency
    # range via _normalize_against, rather than folded into the same
    # _normalize() call above -- a walled candidate's raw values must not
    # be able to widen or shift the range visible results are scored
    # against. Whether one clears the bar is decided once top_score exists
    # (Step 6b), using the identical RELATIVE_KEEP_THRESHOLD "kept" does.
    recency_ref = list(recency_raw.values())
    freq_ref = list(freq_raw.values())
    for c in blocked:
        meta = c["meta"]
        d = _parse_date(meta.get("document_date"))
        breakdown = {
            "similarity": round(c["similarity"], 3),
            "recency": round(_normalize_against(d.timestamp() if d else 0, recency_ref), 3),
            "frequency": round(_normalize_against(float(meta.get("usage_count", 0) or 0), freq_ref), 3),
            "partner_approval": 1.0 if meta.get("partner_approved") is True else 0.0,
            "jurisdiction_match": _jurisdiction_score(meta),
        }
        c["score"] = round(_weighted_score(breakdown, w), 4)

    # --- Step 4: detect clearly superseded / non-approved documents ----
    # resolve_cluster_keys (not a plain per-item cluster_key call) so a
    # document with no usable matter_reference or party names still has a
    # shot at being compared against its real superseding/superseded
    # version via content similarity, instead of always sitting alone in a
    # group of one where supersession can never fire.
    resolved_keys = matters.resolve_cluster_keys([(c["doc_id"], c["meta"]) for c in visible])
    clusters = defaultdict(list)
    for c in visible:
        clusters[resolved_keys[c["doc_id"]]].append(c)

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

    # "kept" is threshold-based, not a fixed top-N: anything scoring within
    # RELATIVE_KEEP_THRESHOLD of the best result in this pool qualifies, so
    # a matter's genuine current version (which already won its own
    # supersession cluster in Step 4) doesn't get bumped into the collapsed
    # "other candidates" list just because unrelated documents from other
    # matters happened to score higher on this particular query. keep_top
    # still caps how many can qualify, so a lenient query can't flood the
    # main results view. `remaining` is already sorted by score descending
    # (carried over from the Step 3 sort; Steps 4-5 only filter, never
    # reorder), so remaining[0] is the top score.
    top_score = remaining[0]["score"] if remaining else 0.0
    threshold = top_score * RELATIVE_KEEP_THRESHOLD
    max_kept = max(req.keep_top, 0)
    kept_raw = [c for c in remaining if c["score"] >= threshold][:max_kept]
    kept_ids = {c["doc_id"] for c in kept_raw}
    other_raw = [c for c in remaining if c["doc_id"] not in kept_ids]

    # --- Step 6b: only disclose a walled candidate if it clears the same
    # bar a visible result has to -- otherwise a walled document that's
    # only an incidental, weak semantic match would surface on every query
    # that so much as brushes its topic, which isn't "this could genuinely
    # help you, go ask a partner," it's noise. top_score == 0 means nothing
    # visible scored at all (e.g. a hard filter emptied the pool), which
    # leaves no legitimate bar to judge a walled candidate against, so none
    # qualify rather than all of them defaulting to "relevant."
    access_restricted = (
        [
            RejectedItem(
                doc_id=c["doc_id"],
                filename=c["meta"].get("filename", c["doc_id"]),
                metadata=DocumentMetadata(**c["meta"]),
                reason="This matter is walled off. You don't have access to view it.",
            )
            for c in blocked
            if c["score"] >= threshold
        ]
        if top_score > 0
        else []
    )

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

    usage_values = {
        c["doc_id"]: float(c["meta"].get("usage_count") or 0)
        for c in visible
    }
    usage_scores = _normalize(usage_values)
    weights = req.weights
    for c in visible:
        meta = c["meta"]
        c["weighted_score"] = (
            c["similarity"] * weights.similarity
            + usage_scores.get(c["doc_id"], 0.5) * weights.frequency
            + (1.0 if meta.get("partner_approved") is True else 0.0) * weights.partner_approval
            + 0.5 * weights.jurisdiction_match
        )

    visible.sort(key=lambda c: c["weighted_score"], reverse=True)
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


def _lineage_family_key(filename: str) -> str:
    """Normalize lifecycle filenames to the underlying document family.

    Matter references group all documents in a file, but a file can contain
    several unrelated documents. Lifecycle prefixes and version markers are
    the reliable family signal available in the current metadata model.
    """
    name = filename.rsplit("/", 1)[-1].lower()
    name = re.sub(r"\.[^.]+$", "", name)
    name = re.sub(r"^\d+[_-]+", "", name)
    name = re.sub(
        r"(?:partner[_-]?)?redlined?|draft(?:ed)?|final(?:i[sz]ed)?|execute(?:d)?|clean(?:ed)?|marked[_-]?up",
        "",
        name,
    )
    name = re.sub(r"(?:^|[_-])v?\d+(?:\.\d+)?(?:[_-]?(?:redlined?|final|draft))?(?=$|[_-])", "", name)
    name = re.sub(r"[_-]+", "_", name).strip("_")
    return name or filename.lower()


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


def _merge_singleton_subfamilies(families: dict) -> dict:
    """A lone document whose normalized family key is a strict subset of
    another family's key *in the same matter* is almost always the same
    underlying document saved under a looser filename, not an unrelated
    one -- e.g. case_documents/MAT-2026-0561's deliberately-misleading
    "07_shareholders_agreement_v2_FINAL_final.docx" (family key
    "shareholders_agreement") is a stale duplicate of
    "05_final_joint_venture_shareholders_agreement.docx" (family key
    "joint_venture_shareholders_agreement"), not a document of its own.
    Folding it in lets it chain as a real "version" edge (with the
    specific supersession reason) instead of falling back to a generic
    "related document" edge. Only merges when exactly one candidate
    superset exists in the matter -- an ambiguous match is left alone
    rather than risk merging two genuinely different documents."""
    names = list(families.keys())
    token_sets = {n: set(n.split("_")) for n in names}
    merged = dict(families)
    for name in names:
        if name not in merged or len(merged[name]) != 1:
            continue
        my_tokens = token_sets[name]
        if not my_tokens:
            continue
        candidates = [
            other for other in names
            if other != name and other in merged and my_tokens < token_sets[other]
        ]
        if len(candidates) == 1:
            merged[candidates[0]].extend(merged.pop(name))
    return merged


def compute_lineage(user_email: str) -> LineageResponse:
    """Corpus-wide view of the same matter-clustering + supersession logic
    run_search uses per-query, exposed as a standalone graph: one cluster
    per matter reference, with solid edges for true version chains and
    dashed related edges connecting other documents in the same matter.
    Matters containing only one document are listed separately.

    Walled matters are excluded entirely before clustering starts, same as
    run_search's access_restricted step, so a walled matter's documents
    never surface in this view for someone outside its allow-list."""
    walls = matters.load_walls()
    records = [
        r
        for r in vectorstore.list_all()
        if not matters.is_blocked(r["metadata"], user_email, walls)
    ]

    # resolve_cluster_keys, not a plain per-record cluster_key call, so a
    # document with no usable matter_reference or party names can still
    # join its real matter's lineage cluster via content similarity rather
    # than always landing in "standalone" (see its docstring). is_blocked
    # above already ran on the plain structural key, per-document, before
    # this -- wall enforcement is untouched by the content-based fallback.
    resolved_keys = matters.resolve_cluster_keys([(r["doc_id"], r["metadata"]) for r in records])
    grouped = defaultdict(list)
    for r in records:
        grouped[resolved_keys[r["doc_id"]]].append(r)

    clusters = []
    standalone = []
    for key, matter_group in grouped.items():
        if len(matter_group) < 2:
            standalone.extend(_to_lineage_node(r) for r in matter_group)
            continue

        families = defaultdict(list)
        for record in matter_group:
            families[_lineage_family_key(record["metadata"].get("filename", record["doc_id"]))].append(record)
        families = _merge_singleton_subfamilies(families)

        def sort_key(r):
            meta = r["metadata"]
            d = _parse_date(meta.get("document_date"))
            return (
                1 if meta.get("partner_approved") is True else 0,
                d.timestamp() if d else 0,
                str(meta.get("version") or ""),
            )

        family_chains = []
        for family_name, family_group in families.items():
            chain = sorted(family_group, key=sort_key)
            family_chains.append((family_name, chain))

        current_record = max(matter_group, key=sort_key)
        ordered_records = []
        edges = []
        for family_name, chain in sorted(family_chains, key=lambda item: min(sort_key(r) for r in item[1])):
            ordered_records.extend(chain)
            edges.extend(
                LineageEdge(
                    from_doc_id=older["doc_id"],
                    to_doc_id=newer["doc_id"],
                    reason=_supersession_reason(newer["metadata"], older["metadata"]),
                    relation="version",
                )
                for older, newer in zip(chain, chain[1:])
            )
            family_current = chain[-1]
            if family_current["doc_id"] != current_record["doc_id"]:
                edges.append(
                    LineageEdge(
                        from_doc_id=family_current["doc_id"],
                        to_doc_id=current_record["doc_id"],
                        reason="related document in the same matter; not a version of the target document",
                        relation="related",
                    )
                )

        client = current_record["metadata"].get("client_name") or "Unnamed client"
        matter = current_record["metadata"].get("matter_type") or "Matter"
        jurisdiction = current_record["metadata"].get("jurisdiction")
        label = f"{client} — {matter} · {jurisdiction}" if jurisdiction else f"{client} — {matter}"
        reference = next((r["metadata"].get("matter_reference") for r in matter_group if r["metadata"].get("matter_reference")), None)
        if reference:
            label = f"{reference} — {label}"

        clusters.append(
            LineageCluster(
                key=key,
                label=label,
                current_doc_id=current_record["doc_id"],
                nodes=[_to_lineage_node(r) for r in ordered_records],
                edges=edges,
            )
        )

    clusters.sort(key=lambda c: len(c.nodes), reverse=True)
    return LineageResponse(clusters=clusters, standalone=standalone)
