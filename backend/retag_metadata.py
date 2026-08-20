"""
Non-destructive metadata refresh: re-runs metadata extraction against
every document ALREADY in the store, using its already-extracted text
(no re-upload needed), and updates it in place by doc_id.

Why this exists: ingestion.py's metadata schema picked up two new fields
(`status`, and a `document_type` restricted to a fixed set of categories)
after most of the current corpus was ingested under the old schema, so
those documents have `status=null` and a free-text `document_type` that
doesn't match the new category list. Since search.py's status/
document_type filters only match on an exact value, that mismatch made
those filters silently exclude the whole pre-existing corpus. This
backfills them without vectorstore.reset() -- unlike seed_demo_data.py
--reset, it never truncates the table, so it's safe to run while other
ingests are happening against the same store: it only UPSERTs the doc_ids
it already fetched, and never deletes anything.

    python retag_metadata.py
"""
from app import ingestion, vectorstore


def main():
    records = vectorstore.list_all()
    print(f"Re-tagging metadata for {len(records)} documents ...")
    updated = 0
    for r in records:
        doc_id, text, meta = r["doc_id"], r["text"], r["metadata"]
        try:
            fresh = ingestion.extract_metadata_with_llm(meta.get("filename", doc_id), text)
        except Exception as e:  # noqa: BLE001
            print(f"  ! metadata extraction failed for {meta.get('filename', doc_id)}: {e}")
            continue
        fresh_dict = fresh.model_dump()
        # Preserve fields the LLM doesn't know about / shouldn't overwrite.
        fresh_dict["filename"] = meta.get("filename", doc_id)
        fresh_dict["usage_count"] = meta.get("usage_count", 0)
        if meta.get("matter_reference"):
            fresh_dict["matter_reference"] = meta["matter_reference"]
        vectorstore.add_document(doc_id, text, fresh_dict)
        updated += 1
        print(f"  + {fresh_dict['filename']:55s} document_type={fresh.document_type!r} status={fresh.status!r}")

    print(f"Done. Re-tagged {updated}/{len(records)} documents.")


if __name__ == "__main__":
    main()
