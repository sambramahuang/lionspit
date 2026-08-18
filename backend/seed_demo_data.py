"""
Seeds the demo_corpus/ folder straight into the vector store, without
needing the API server running. Handy for resetting right before a demo
run. From backend/, with your virtualenv active and .env filled in:

    python seed_demo_data.py           # ingest everything in demo_corpus/
    python seed_demo_data.py --reset   # wipe the index first, then ingest
"""
import sys
from pathlib import Path

from app import conflicts, ingestion, matters, vectorstore

CORPUS_DIR = Path(__file__).resolve().parent / "demo_corpus"


def main():
    if "--reset" in sys.argv:
        print("Resetting existing index...")
        vectorstore.reset()

    files = sorted(CORPUS_DIR.glob("*.txt"))
    if not files:
        print(f"No .txt files found in {CORPUS_DIR}")
        return

    print(f"Seeding {len(files)} documents from {CORPUS_DIR} ...")
    for path in files:
        content = path.read_bytes()
        text = ingestion.extract_text(path.name, content)
        try:
            metadata = ingestion.extract_metadata_with_llm(path.name, text)
        except Exception as e:  # noqa: BLE001
            print(f"  ! metadata extraction failed for {path.name}: {e}")
            continue
        doc_id = ingestion.new_doc_id()
        meta_dict = metadata.model_dump()
        meta_dict["filename"] = path.name
        meta_dict["usage_count"] = 0
        vectorstore.add_document(doc_id, text, meta_dict)
        clauses = ingestion.split_into_clauses(text)
        vectorstore.add_document_clauses(doc_id, clauses)

        new_matter_key = matters.cluster_key(meta_dict)
        found_conflicts = conflicts.detect_conflicts(meta_dict, new_matter_key)
        for c in found_conflicts:
            vectorstore.flag_conflict(new_matter_key, c["reason"], doc_id)

        conflict_note = f", CONFLICT FLAGGED: {found_conflicts[0]['reason'][:60]}..." if found_conflicts else ""
        print(f"  + {path.name:45s} -> {doc_id}  "
              f"[{metadata.document_type or '?'}, {metadata.document_date or '?'}, "
              f"partner_approved={metadata.partner_approved}, {len(clauses)} clauses]{conflict_note}")

    print("Done. Start the API with: uvicorn app.main:app --reload --port 8000")


if __name__ == "__main__":
    main()
