"""Add the generated demo corpus without resetting existing documents.

Run from backend/ with the backend environment configured:
    python ingest_generated_data.py

The importer deliberately targets only the four generated matter folders and
skips any filename already present in the shared vector store. It uses the
same extraction, embedding, clause, lineage and conflict paths as the live
application while pinning the known matter-level facts so the synthetic demo
relationships remain deterministic.
"""
from pathlib import Path

from app import conflicts, ingestion, matters, vectorstore

CORPUS_DIR = Path(__file__).resolve().parent.parent / "case_documents"
GENERATED_MATTERS = {
    "MAT-2026-0601": {
        "client_name": "HelioGrid Energy Pte Ltd",
        "counterparty_name": "Meridian Infrastructure Holdings Pte Ltd",
        "matter_type": "Corporate and M&A",
        "practice_area": "Corporate and M&A",
        "jurisdiction": "Singapore",
    },
    "MAT-2026-0602": {
        "client_name": "Meridian Infrastructure Holdings Pte Ltd",
        "counterparty_name": "Eastbank Utilities Ltd",
        "matter_type": "Energy dispute",
        "practice_area": "Dispute resolution and energy regulation",
        "jurisdiction": "Singapore",
    },
    "MAT-2026-0603": {
        "client_name": "LumenArc Technologies Pte Ltd",
        "counterparty_name": "Cedar Ventures Fund II LP",
        "matter_type": "Venture financing",
        "practice_area": "Corporate, venture financing and securities",
        "jurisdiction": "Singapore",
    },
    "MAT-2026-0604": {
        "client_name": "Northstar Health Systems Pte Ltd",
        "counterparty_name": "CloudMosaic Solutions Pte Ltd",
        "matter_type": "Technology and privacy",
        "practice_area": "Technology, privacy and data protection",
        "jurisdiction": "Singapore",
    },
}

OVERRIDES = {
    "02_asset_purchase_agreement_draft_v1.txt": {"document_type": "Contracts / Agreements", "version": "1.0", "is_draft_or_model": "draft", "partner_approved": False, "document_date": "2026-02-03"},
    "03_asset_purchase_agreement_partner_redline_v2.txt": {"document_type": "Contracts / Agreements", "version": "2.0", "is_draft_or_model": "draft", "partner_approved": False, "document_date": "2026-02-19"},
    "04_executed_asset_purchase_agreement_v3.txt": {"document_type": "Contracts / Agreements", "version": "3.0", "is_draft_or_model": "executed", "partner_approved": True, "document_executed": True, "document_date": "2026-03-31"},
    "02_grid_services_termination_advice_draft.txt": {"document_type": "Legal opinions", "version": "1.0", "is_draft_or_model": "draft", "partner_approved": False, "document_date": "2026-02-02"},
    "03_grid_services_termination_advice_final.txt": {"document_type": "Legal opinions", "version": "2.0", "is_draft_or_model": "executed", "partner_approved": True, "document_date": "2026-02-20"},
    "02_series_b_investment_agreement_draft.txt": {"document_type": "Contracts / Agreements", "version": "1.0", "is_draft_or_model": "draft", "partner_approved": False, "document_date": "2026-02-15"},
    "03_shareholders_agreement_partner_redline.txt": {"document_type": "Contracts / Agreements", "version": "1.0-redline", "is_draft_or_model": "draft", "partner_approved": False, "document_date": "2026-03-18"},
    "04_executed_shareholders_agreement.txt": {"document_type": "Contracts / Agreements", "version": "2.0", "is_draft_or_model": "executed", "partner_approved": True, "document_executed": True, "document_date": "2026-06-30"},
    "02_privacy_breach_legal_advice_draft.txt": {"document_type": "Legal opinions", "version": "1.0", "is_draft_or_model": "draft", "partner_approved": False, "document_date": "2026-02-08"},
    "03_privacy_breach_legal_advice_final.txt": {"document_type": "Legal opinions", "version": "2.0", "is_draft_or_model": "executed", "partner_approved": True, "document_date": "2026-02-14"},
}


def main():
    existing_names = {
        str(record["metadata"].get("filename") or "")
        for record in vectorstore.list_all()
    }
    files = []
    for matter in GENERATED_MATTERS:
        folder = CORPUS_DIR / matter
        files.extend(sorted(folder.glob("*.txt")))

    print(f"Found {len(files)} generated documents; existing indexed names: {len(existing_names)}")
    added = 0
    skipped = 0
    for path in files:
        display_name = f"{path.parent.name}/{path.name}"
        if display_name in existing_names:
            print(f"  = skip existing {display_name}")
            skipped += 1
            continue

        text = ingestion.extract_text(path.name, path.read_bytes())
        matter_meta = GENERATED_MATTERS[path.parent.name]
        try:
            metadata = ingestion.extract_metadata_with_llm(path.name, text)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! metadata extraction failed for {display_name}: {exc}")
            continue

        meta = metadata.model_dump()
        meta.update(matter_meta)
        meta["matter_reference"] = path.parent.name
        meta["filename"] = display_name
        meta["usage_count"] = 0
        meta.update(OVERRIDES.get(path.name, {}))

        doc_id = ingestion.new_doc_id()
        vectorstore.add_document(doc_id, text, meta)
        clauses = ingestion.split_into_clauses(text)
        vectorstore.add_document_clauses(doc_id, clauses)

        matter_key = matters.cluster_key(meta)
        found_conflicts = conflicts.detect_conflicts(meta, matter_key)
        for conflict in found_conflicts:
            vectorstore.flag_conflict(matter_key, conflict["reason"], doc_id)
        note = f" CONFLICT: {found_conflicts[0]['reason'][:100]}" if found_conflicts else ""
        print(f"  + {display_name} -> {doc_id} [{meta.get('document_type')}, v{meta.get('version')}]" + note)
        added += 1

    print(f"Done. Added {added}; skipped {skipped}; originals were not deleted.")


if __name__ == "__main__":
    main()
