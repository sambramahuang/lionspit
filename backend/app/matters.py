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
from collections import defaultdict

from app import vectorstore
from app.models import ConflictFlag, MatterSummary, MatterWallInfo


def _normalize_reference(ref: str) -> str:
    # Strips everything but the code itself so formatting noise ("HC/S
    # 214/2026" vs "HC-S-214-2026" vs "HC S 214 2026") doesn't fracture one
    # matter into several -- same idea as case-folding a name, just for a
    # reference code instead of free text.
    return re.sub(r"[^a-z0-9]", "", ref.lower())


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

    When neither a reference number nor a party name is available there
    isn't enough signal to safely group the document with anything, so it
    gets a key unique to itself."""
    ref = _normalize_reference(str(meta.get("matter_reference") or "").strip())
    if ref:
        return f"ref|{ref}"

    parties = sorted({
        p for p in (
            str(meta.get("client_name", "")).lower().strip(),
            str(meta.get("counterparty_name", "")).lower().strip(),
        ) if p
    })
    matter = str(meta.get("matter_type", "")).lower().strip()
    if not parties or not matter:
        return f"__unclustered__|{meta.get('filename', '')}"
    jurisdiction = str(meta.get("jurisdiction", "")).lower().strip()
    return "|".join(parties + [matter, jurisdiction])


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
    UI. Partners see every matter (including ones they're personally
    walled from) so they can audit/manage wall config; non-partners only
    see matters they're not blocked from, so a walled matter's existence
    and label aren't leaked to someone outside its allow-list. Same
    visibility rule extends to conflict flags -- they're matter-level
    facts, shown wherever the matter itself is shown."""
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
            continue

        wall = walls.get(key)
        conflict = conflicts.get(key)
        first = group[0]["metadata"]
        client = first.get("client_name") or "Unnamed client"
        matter_type = first.get("matter_type") or "Matter"
        jurisdiction = first.get("jurisdiction")
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
