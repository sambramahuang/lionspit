"""
Automatic conflict-of-interest detection -- the one piece of the brief's
"conflict boundaries" language that matter walls (matters.py) don't cover
on their own: walls are entirely manual, set by a partner after the fact.
This runs at ingest time and only ever *suggests*; a partner still
reviews and decides on the Matters page (see MatterSummary.conflict) --
nothing here creates or edits a wall automatically.

Detection is deliberately simple for a first pass: exact (case
-insensitive) name matching, not entity resolution. "Alpha Robotics Pte
Ltd" and "Alpha Robotics" won't be recognized as the same company, same
limitation cluster_key already has. That's an honest bound on this
being a "first pass," not a full conflicts-database replacement.
"""
from collections import defaultdict

from app import matters, vectorstore


def _name(meta: dict, field: str) -> str:
    return str(meta.get(field) or "").strip().lower()


def detect_conflicts(new_doc_meta: dict, new_matter_key: str) -> list[dict]:
    """Checks the new document's client/counterparty against every OTHER
    matter's client/counterparty for the classic positional-conflict
    pattern: the new matter's party appears on the opposite side of an
    existing, unrelated matter -- i.e. the firm may now be adverse to an
    existing client, or representing someone it was previously adverse
    to. Returns one entry per distinct other matter implicated, not one
    per document, so a 5-document matter doesn't produce 5 duplicate
    warnings.

    Deliberately scans the WHOLE corpus, including matters walled off
    from the uploader -- this is not an oversight. Conflict checking is
    exactly the kind of firm-wide compliance function that needs
    visibility across ethical walls to work at all; a wall hiding a
    matter from a given lawyer must not also hide it from the conflict
    check, or the two features would defeat each other.
    """
    new_client = _name(new_doc_meta, "client_name")
    new_counterparty = _name(new_doc_meta, "counterparty_name")
    if not new_client and not new_counterparty:
        return []

    by_matter: dict = defaultdict(list)
    for r in vectorstore.list_all():
        key = matters.cluster_key(r["metadata"])
        if key == new_matter_key:
            continue
        by_matter[key].append(r["metadata"])

    conflicts = []
    for key, metas in by_matter.items():
        for meta in metas:
            existing_client = _name(meta, "client_name")
            existing_counterparty = _name(meta, "counterparty_name")

            if new_client and new_client == existing_counterparty:
                conflicts.append({
                    "matter_key": key,
                    "reason": (
                        f'The new document\'s client, "{new_doc_meta.get("client_name")}", '
                        f'appears as the counterparty in another matter ("{meta.get("client_name")} '
                        f'v. {meta.get("counterparty_name")}" -- {meta.get("matter_type") or "matter"}). '
                        "Possible conflict: the firm may already be adverse to this party."
                    ),
                })
                break
            if new_counterparty and new_counterparty == existing_client:
                conflicts.append({
                    "matter_key": key,
                    "reason": (
                        f'The new document\'s counterparty, "{new_doc_meta.get("counterparty_name")}", '
                        f'is an existing client in another matter ("{meta.get("client_name")} — '
                        f'{meta.get("matter_type") or "matter"}"). '
                        "Possible conflict: this may put the firm adverse to an existing client."
                    ),
                })
                break

    return conflicts
