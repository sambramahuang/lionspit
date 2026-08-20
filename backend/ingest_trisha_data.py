"""Adds the services & distributorship set (contributed by Trisha, folded
into case_documents/README.md's "Ground truth — services & distributorship
set" section) without touching or duplicating anything already indexed.

Same non-destructive pattern as ingest_generated_data.py: skips any
filename already present in the shared vector store, so it's safe to
re-run and safe to run against a corpus that's already been seeded.

Run from backend/, with the backend environment configured:
    python ingest_trisha_data.py
"""
from pathlib import Path

from app import conflicts, ingestion, matters, vectorstore

CORPUS_DIR = Path(__file__).resolve().parent.parent / "case_documents"
TRISHA_MATTERS = [
    "MAT-2026-0544",
    "MAT-2026-0577",
    "MAT-2026-0588",
    "MAT-2026-0631",
    "MAT-2026-0654",
    "MAT-2026-0699",
]
_EXTENSIONS = {".pdf", ".docx", ".txt"}


def main():
    existing_names = {
        str(record["metadata"].get("filename") or "")
        for record in vectorstore.list_all()
    }

    files = []
    for matter in TRISHA_MATTERS:
        folder = CORPUS_DIR / matter
        if not folder.is_dir():
            print(f"  ! expected folder not found: {folder}")
            continue
        files.extend(sorted(p for p in folder.iterdir() if p.suffix.lower() in _EXTENSIONS))

    print(f"Found {len(files)} documents across {len(TRISHA_MATTERS)} matters; existing indexed names: {len(existing_names)}")
    added = 0
    skipped = 0
    for path in files:
        display_name = f"{path.parent.name}/{path.name}"
        if display_name in existing_names:
            print(f"  = skip existing {display_name}")
            skipped += 1
            continue

        content = path.read_bytes()
        text = ingestion.extract_text(path.name, content)
        if not text.strip():
            print(f"  ! no extractable text (even after OCR fallback) for {display_name}")
            continue

        try:
            metadata = ingestion.extract_metadata_with_llm(path.name, text)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! metadata extraction failed for {display_name}: {exc}")
            continue

        meta = metadata.model_dump()
        meta["filename"] = display_name
        meta["usage_count"] = 0
        # Same convention as seed_demo_data.py: the folder IS the firm's
        # matter reference, a stronger and more consistent signal than
        # whatever the LLM inferred from six differently-worded documents.
        meta["matter_reference"] = path.parent.name

        doc_id = ingestion.new_doc_id()
        vectorstore.add_document(doc_id, text, meta)
        clauses = ingestion.split_into_clauses(text)
        vectorstore.add_document_clauses(doc_id, clauses)

        matter_key = matters.cluster_key(meta)
        found_conflicts = conflicts.detect_conflicts(meta, matter_key)
        for conflict in found_conflicts:
            vectorstore.flag_conflict(matter_key, conflict["reason"], doc_id)
        note = f" CONFLICT: {found_conflicts[0]['reason'][:100]}" if found_conflicts else ""
        print(f"  + {display_name} -> {doc_id} [{meta.get('document_type')}, v{meta.get('version')}, {len(clauses)} clauses]" + note)
        added += 1

    print(f"Done. Added {added}; skipped {skipped}; nothing existing was touched.")


if __name__ == "__main__":
    main()
