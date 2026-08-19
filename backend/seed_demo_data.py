"""
Seeds the case_documents/ corpus straight into the vector store, without
needing the API server running. Handy for resetting right before a demo
run. From backend/, with your virtualenv active and .env filled in:

    python seed_demo_data.py           # ingest everything in case_documents/
    python seed_demo_data.py --reset   # wipe the index first, then ingest

Deliberately does NOT touch live_ingest_demo/ -- that file is meant to be
ingested live, through the UI, during the demo itself (see its own
docstring and the README's conflict-detection demo step), not folded into
the seeded baseline.
"""
import sys
from pathlib import Path

from app import conflicts, ingestion, matters, vectorstore

CORPUS_DIR = Path(__file__).resolve().parent.parent / "case_documents"
_EXTENSIONS = {".pdf", ".docx", ".txt"}

# These two are deliberately filed in a matter's folder while explicitly
# being a DIFFERENT matter (case_documents/README.md calls them out as
# same-folder cross-matter distractors -- the charterparty redline names
# its own separate matter number in its own text; the draft supply
# agreement names a different counterparty entirely). Forcing the folder's
# matter_reference onto them would silently merge them into their folder's
# main matter and defeat the point of including them, so they're left to
# fall back to ordinary party-name-based clustering instead.
_CROSS_MATTER_DISTRACTORS = {
    "HC-S-214-2026/05_draft_contract_2026_supply_agreement.docx",
    "HC-ADM-88-2026/05_redlined_charterparty_agreement.docx",
}


def main():
    if "--reset" in sys.argv:
        print("Resetting existing index...")
        vectorstore.reset()

    files = sorted(
        (p for p in CORPUS_DIR.rglob("*") if p.suffix.lower() in _EXTENSIONS),
        key=lambda p: (p.parent.name, p.name),
    )
    if not files:
        print(f"No .pdf/.docx/.txt files found under {CORPUS_DIR}")
        return

    print(f"Seeding {len(files)} documents from {CORPUS_DIR} ...")
    for path in files:
        # Prefix with the matter folder (a real court suit/matter reference
        # number, per case_documents/README.md) since every matter reuses
        # the same filenames (01_client_correspondence.pdf, etc.) -- without
        # this, the Library view would show five indistinguishable files
        # all named "01_client_correspondence.pdf".
        display_name = f"{path.parent.name}/{path.name}"
        content = path.read_bytes()
        text = ingestion.extract_text(path.name, content)
        try:
            # Pass the bare filename to the LLM, not display_name -- the
            # folder prefix IS the matter reference for most files here, so
            # including it in the "Filename:" hint would leak the answer
            # into extraction and defeat the point of the two cross-matter
            # distractors deliberately filed under the "wrong" folder.
            metadata = ingestion.extract_metadata_with_llm(path.name, text)
        except Exception as e:  # noqa: BLE001
            print(f"  ! metadata extraction failed for {display_name}: {e}")
            continue
        doc_id = ingestion.new_doc_id()
        meta_dict = metadata.model_dump()
        meta_dict["filename"] = display_name
        meta_dict["usage_count"] = 0
        # case_documents/README.md documents this dataset's own convention:
        # each top-level folder IS the court suit/summons number or firm
        # matter reference, deliberately (not by client name), matching how
        # a real firm's shared drive is organised. That's a stronger,
        # guaranteed-consistent signal than asking the LLM to spot and
        # normalize the same reference number across six differently
        # -formatted documents, so it wins over whatever (if anything) the
        # LLM extracted from the document text -- see matters.cluster_key.
        if display_name not in _CROSS_MATTER_DISTRACTORS:
            meta_dict["matter_reference"] = path.parent.name
        vectorstore.add_document(doc_id, text, meta_dict)
        clauses = ingestion.split_into_clauses(text)
        vectorstore.add_document_clauses(doc_id, clauses)

        new_matter_key = matters.cluster_key(meta_dict)
        found_conflicts = conflicts.detect_conflicts(meta_dict, new_matter_key)
        for c in found_conflicts:
            vectorstore.flag_conflict(new_matter_key, c["reason"], doc_id)

        conflict_note = f", CONFLICT FLAGGED: {found_conflicts[0]['reason'][:60]}..." if found_conflicts else ""
        print(f"  + {display_name:55s} -> {doc_id}  "
              f"[{metadata.document_type or '?'}, {metadata.document_date or '?'}, "
              f"partner_approved={metadata.partner_approved}, {len(clauses)} clauses]{conflict_note}")

    print("Done. Start the API with: uvicorn app.main:app --reload --port 8000")


if __name__ == "__main__":
    main()
