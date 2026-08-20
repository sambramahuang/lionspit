"""
Matter clustering + ethical-wall enforcement. `cluster_key` defines what a
"matter" is (see docstring below) and is the single source of truth for it
-- search.py's supersession clustering, compute_lineage's version graph,
and the wall-check functions here all call the same function so a matter
is identified identically everywhere. Every place that returns documents
to the frontend (search, document list/get, lineage, draft) goes through
is_blocked()/is_key_blocked() here instead of re-implementing the check.
"""
import re
from collections import Counter, defaultdict

from app import vectorstore
from app.models import ConflictFlag, MatterSummary, MatterWallInfo


def _most_common(values) -> str | None:
    """Most-frequent non-empty value in `values`, or None. Ties break on
    whichever value Counter.most_common() saw first, which is stable
    insertion order in CPython -- fine here since a tie means the
    documents in the group didn't agree in the first place."""
    counts = Counter(v for v in values if v)
    return counts.most_common(1)[0][0] if counts else None


def _normalize_reference(ref: str) -> str:
    # Strips everything but the code itself so formatting noise ("HC/S
    # 214/2026" vs "HC-S-214-2026" vs "HC S 214 2026") doesn't fracture one
    # matter into several -- same idea as case-folding a name, just for a
    # reference code instead of free text.
    return re.sub(r"[^a-z0-9]", "", ref.lower())


# Legal entity-type suffixes only -- deliberately NOT stripping generic
# business words like "Holdings"/"Group"/"Partners", which are routinely
# part of the substantive name itself (e.g. "Meridian Infrastructure
# Holdings" -- stripping "Holdings" there would silently rename the
# company). Applied repeatedly so a name with two suffixes in a row
# ("... Pte Ltd Co") still fully resolves.
_ENTITY_SUFFIX_RE = re.compile(
    r"[,.\s]*\b("
    r"pte\.?\s*ltd\.?|private\s+limited|ltd\.?|llc|llp|inc\.?|incorporated|"
    r"corp\.?|corporation|plc|limited|co\.?"
    r")\.?\s*$",
    re.IGNORECASE,
)


def _normalize_party_name(name: str) -> str:
    """Case/punctuation/entity-suffix-insensitive form of a party name, so
    "Alpha Robotics Pte Ltd" and "Alpha Robotics Pte. Ltd." (or a bare
    "Alpha Robotics" from a document that just never states the suffix)
    still cluster as the same party instead of fracturing a matter across
    two keys purely on formatting noise."""
    name = name.strip()
    prev = None
    while prev != name:
        prev = name
        name = _ENTITY_SUFFIX_RE.sub("", name).strip()
    return re.sub(r"\s+", " ", name).lower()


# Cosine distance (pgvector's `<=>` operator) below which two documents'
# full-text embeddings are treated as "the same underlying document,
# messily re-saved" -- the only case resolve_cluster_keys uses content
# similarity for (see its docstring). Calibrated against this corpus's own
# documents, not guessed: MAT-2026-0561's genuine near-duplicate pair
# (05_final vs the deliberately-planted 07_stale-duplicate trap) sits at
# ~0.09, and a same-matter draft-vs-final pair sits at ~0.08 -- but two
# DIFFERENT matters' same-template document (e.g. both litigation sets'
# draft specific-production submissions, which share most of their
# boilerplate) sits at ~0.18. 0.13 sits with real margin above the
# same-document cluster and real margin below the different-matter
# same-template cluster. Note this is NOT a general "same matter" signal --
# same-matter documents of *different* types (e.g. a matter's own client
# correspondence vs its billing summary) measured ~0.27, well outside any
# safe threshold -- structured fields (matter_reference, party names) stay
# the primary signal for that; this only catches near-duplicate re-saves.
CONTENT_CLUSTER_MAX_DISTANCE = 0.13


def cluster_key(meta: dict) -> str:
    """Same-matter grouping so we can compare versions against each other
    rather than against the whole corpus.

    Prefers the firm's own matter/case reference number (matter_reference)
    when the document states one: a real case file mixes document types --
    client correspondence, a billing summary, a draft, a final/executed
    version, an internal memo -- and the metadata LLM can reasonably tag
    those with different matter_type or even practice_area guesses even
    though they're unambiguously the same file. A billing summary isn't
    "about" litigation the way a court submission is, but it belongs to the
    exact same matter. An explicit, firm-assigned reference number is a
    stronger and type-agnostic signal of "same matter" than an inferred
    combination of party names + document category ever can be, so it wins
    when present.

    Falls back to the previous heuristic -- the *unordered set* of
    client_name + counterparty_name, plus matter_type + jurisdiction -- for
    documents that don't cite a reference number (most informal
    correspondence, or a brand-new matter that hasn't been assigned one
    yet). matter_type/jurisdiction alone are category-level, not
    matter-level, so two unrelated clients' documents of the same type
    (e.g. two different companies' shareholders' agreements) must never
    merge into one lineage this way. Matching on the *pair* of party names
    rather than client_name alone is robust to extraction not always being
    able to tell which party is "the client" (e.g. a tenancy renewal might
    get filed with the tenant as client_name while the original lease got
    filed with the landlord as client_name) -- both documents still name
    the same two parties either way.

    Party names are compared entity-suffix-insensitively (see
    _normalize_party_name) so "Alpha Robotics Pte Ltd" and a document that
    just calls it "Alpha Robotics" still count as the same party -- messy,
    inconsistent naming shouldn't fracture a matter into two clusters over
    formatting alone.

    When neither a reference number nor a party name is available there
    isn't enough signal to safely group the document with anything from
    structured fields alone -- see resolve_cluster_keys for the content
    -based fallback batch callers should use instead of trusting this
    "unclustered" key as final."""
    ref = _normalize_reference(str(meta.get("matter_reference") or "").strip())
    if ref:
        return f"ref|{ref}"

    parties = sorted({
        p for p in (
            _normalize_party_name(str(meta.get("client_name", ""))),
            _normalize_party_name(str(meta.get("counterparty_name", ""))),
        ) if p
    })
    matter = str(meta.get("matter_type", "")).lower().strip()
    if not parties or not matter:
        return f"__unclustered__|{meta.get('filename', '')}"
    jurisdiction = str(meta.get("jurisdiction", "")).lower().strip()
    return "|".join(parties + [matter, jurisdiction])


def resolve_cluster_keys(items: list[tuple[str, dict]]) -> dict[str, str]:
    """cluster_key(meta), except documents with neither a usable
    matter_reference nor usable party names (cluster_key's "__unclustered__"
    case) get a second chance: compared by full-document embedding
    similarity against the rest of the corpus, and merged into the nearest
    sufficiently-similar OTHER document's key if one exists (see
    CONTENT_CLUSTER_MAX_DISTANCE for how "sufficiently similar" is
    calibrated, and why it's deliberately narrow -- a near-duplicate re-save
    only, not a general same-matter classifier).

    This is the fallback for real-world messy uploads that don't cite a
    reference number and don't name their parties consistently (or at all)
    -- e.g. a bare internal file note with no header. Structured fields
    still do almost all of the work; this only catches what they can't.

    `items` is (doc_id, metadata) pairs for one batch of same-corpus
    records (a search's candidate pool, or the whole visible corpus for
    lineage/matters) -- NOT the single-document cluster_key/is_blocked
    path. Deliberately not wired into is_blocked(): wall enforcement stays
    on the plain structural key, so a fuzzy content match never changes
    what a document is judged to be for access-control purposes, only for
    grouping in search ranking and the lineage graph."""
    keys = {doc_id: cluster_key(meta) for doc_id, meta in items}
    unclustered_ids = [doc_id for doc_id, key in keys.items() if key.startswith("__unclustered__")]
    for doc_id in unclustered_ids:
        for neighbor in vectorstore.nearest_neighbors(doc_id, limit=5):
            if neighbor["distance"] > CONTENT_CLUSTER_MAX_DISTANCE:
                break  # nearest_neighbors is sorted ascending -- nothing closer follows
            neighbor_key = keys.get(neighbor["doc_id"])
            if neighbor_key and not neighbor_key.startswith("__unclustered__"):
                keys[doc_id] = neighbor_key
                break
    return keys


def load_walls() -> dict:
    """All configured walls, keyed by matter_key -- fetched once per
    request and reused across every document being checked, instead of one
    DB round-trip per document."""
    return vectorstore.list_walls()


def is_key_blocked(key: str, user_email: str, walls: dict) -> bool:
    wall = walls.get(key)
    if not wall or not wall.get("walled"):
        return False
    allowed = {e.strip().lower() for e in wall.get("allowed_emails") or []}
    return user_email.strip().lower() not in allowed


def is_blocked(meta: dict, user_email: str, walls: dict) -> bool:
    """True if the matter this document belongs to is walled and the given
    (verified) email is not on its allow-list. Applies uniformly regardless
    of partner status -- a partner administering walls does not thereby get
    to see the content of a matter they're personally walled off from; that
    would defeat the point of an ethical wall. Partner status only grants
    permission to *edit* wall config (see require_partner) and to see wall
    metadata for matters they're blocked from in summarize() below, not
    their document content."""
    return is_key_blocked(cluster_key(meta), user_email, walls)


def summarize(user_email: str, is_partner: bool) -> list[MatterSummary]:
    """One row per matter that has at least one document, for the Matters
    UI. Every matter gets a row for every viewer -- a walled matter's
    existence isn't hidden, matching how a walled document itself is now
    listed in /api/documents (see main.py's list_documents). What's
    withheld from a blocked non-partner is everything a wall exists to
    protect: the client/counterparty-revealing label, the allow-list (who
    else can see it), and any conflict-flag reason (which names both
    sides of the conflict). Partners see full detail on every matter,
    including ones they're personally walled from, so they can audit/
    manage wall config."""
    records = vectorstore.list_all()
    walls = load_walls()
    conflicts = vectorstore.list_conflicts()

    grouped: dict = defaultdict(list)
    for r in records:
        grouped[cluster_key(r["metadata"])].append(r)

    out = []
    for key, group in grouped.items():
        blocked = is_key_blocked(key, user_email, walls)
        if blocked and not is_partner:
            out.append(MatterSummary(
                matter_key=key,
                label="Walled matter",
                document_count=len(group),
                wall=MatterWallInfo(matter_key=key, walled=True, allowed_emails=[]),
                conflict=None,
                access_restricted=True,
            ))
            continue

        wall = walls.get(key)
        conflict = conflicts.get(key)
        # Majority vote across every document in the group, not group[0] --
        # `records` comes straight from an unordered `SELECT ... FROM
        # documents`, so "the first row Postgres happens to return" is
        # arbitrary, and a single outlier extraction (e.g. an internal file
        # note whose text reads more firm-centrically, or a contract naming
        # the counterparty as prominently as the client) could otherwise
        # mislabel the whole matter row even though most of its documents
        # agree on the real client_name/matter_type/jurisdiction.
        client = _most_common(g["metadata"].get("client_name") for g in group) or "Unnamed client"
        matter_type = _most_common(g["metadata"].get("matter_type") for g in group) or "Matter"
        jurisdiction = _most_common(g["metadata"].get("jurisdiction") for g in group)
        label = f"{client} — {matter_type} · {jurisdiction}" if jurisdiction else f"{client} — {matter_type}"
        # Surface the reference actually driving the grouping (see
        # cluster_key) so a mixed-document-type matter's label doesn't look
        # arbitrary -- it's the same explicit case/matter number every
        # document in the group cites, not an inferred guess.
        reference = next((g["metadata"].get("matter_reference") for g in group if g["metadata"].get("matter_reference")), None)
        if reference:
            label = f"{reference} — {label}"

        out.append(MatterSummary(
            matter_key=key,
            label=label,
            document_count=len(group),
            wall=MatterWallInfo(
                matter_key=key,
                walled=bool(wall["walled"]) if wall else False,
                allowed_emails=wall["allowed_emails"] if wall else [],
                updated_by=wall["updated_by"] if wall else None,
                updated_at=wall["updated_at"] if wall else None,
            ),
            conflict=ConflictFlag(**conflict) if conflict else None,
        ))

    # Unresolved conflicts surface first -- that's the whole point of
    # detecting them automatically, they shouldn't get buried alphabetically.
    out.sort(key=lambda m: (not (m.conflict and not m.conflict.acknowledged), m.label.lower()))
    return out
