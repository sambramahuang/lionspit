-- Run once in the Supabase SQL editor, same as matter_walls.sql.
--
-- One row per clause/section a document was split into at ingest time
-- (see app/ingestion.py:split_into_clauses). Embedded and indexed
-- separately from the whole-document row in `documents` so a lawyer can
-- search for "the indemnity cap clause" and land on the exact paragraph,
-- not just the 40-page agreement it's buried in.

CREATE TABLE IF NOT EXISTS document_clauses (
    id            bigserial PRIMARY KEY,
    doc_id        text NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    clause_index  integer NOT NULL,
    label         text,
    text          text NOT NULL,
    embedding     vector(1536) NOT NULL
);

CREATE INDEX IF NOT EXISTS document_clauses_doc_id_idx ON document_clauses (doc_id);
