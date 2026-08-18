-- Run once in the Supabase SQL editor, same pattern as matter_walls.sql
-- and document_clauses.sql.
--
-- One row per matter with an unresolved (or previously resolved)
-- conflict-of-interest flag. Populated automatically by
-- app/conflicts.py:detect_conflicts at ingest time -- never auto-applied
-- as a wall, just surfaced here for a partner to review on the Matters
-- page. flagged_doc_id is informational only (no FK): the flag is a
-- fact about the matter, and should survive even if that specific
-- document is later deleted.

CREATE TABLE IF NOT EXISTS matter_conflict_flags (
    matter_key       text PRIMARY KEY,
    reason           text NOT NULL,
    flagged_doc_id   text,
    detected_at      timestamptz NOT NULL DEFAULT now(),
    acknowledged     boolean NOT NULL DEFAULT false,
    acknowledged_by  text,
    acknowledged_at  timestamptz
);
