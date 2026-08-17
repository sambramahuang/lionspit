"""
Matter clustering + ethical-wall enforcement. `cluster_key` defines what a
"matter" is (see docstring below) and is the single source of truth for it
-- search.py's supersession clustering, compute_lineage's version graph,
and the wall-check functions here all call the same function so a matter
is identified identically everywhere. Every place that returns documents
to the frontend (search, document list/get, lineage, draft) goes through
is_blocked()/is_key_blocked() here instead of re-implementing the check.
"""
from collections import defaultdict

from app import vectorstore
from app.models import MatterSummary, MatterWallInfo


def cluster_key(meta: dict) -> str:
    """Same-matter grouping so we can compare versions against each other
    rather than against the whole corpus. Requires matching named parties --
    matter_type/jurisdiction alone are category-level, not matter-level, so
    two unrelated clients' documents of the same type (e.g. two different
    companies' shareholders' agreements) must never merge into one lineage.

    Matches on the *unordered set* of client_name + counterparty_name rather
    than client_name alone: when a document names two parties, extraction
    can't always tell which one is "the client" (e.g. a tenancy renewal
    might get filed with the tenant as client_name while the original lease
    got filed with the landlord as client_name) -- matching on the pair is
    robust to that, since both documents still name the same two parties.

    When no party name is available there isn't enough signal to safely
    group the document with anything, so it gets a key unique to itself."""
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
    and label aren't leaked to someone outside its allow-list."""
    records = vectorstore.list_all()
    walls = load_walls()

    grouped: dict = defaultdict(list)
    for r in records:
        grouped[cluster_key(r["metadata"])].append(r)

    out = []
    for key, group in grouped.items():
        blocked = is_key_blocked(key, user_email, walls)
        if blocked and not is_partner:
            continue

        wall = walls.get(key)
        first = group[0]["metadata"]
        client = first.get("client_name") or "Unnamed client"
        matter_type = first.get("matter_type") or "Matter"
        jurisdiction = first.get("jurisdiction")
        label = f"{client} — {matter_type} · {jurisdiction}" if jurisdiction else f"{client} — {matter_type}"

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
        ))

    out.sort(key=lambda m: m.label.lower())
    return out
