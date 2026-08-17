-- Run once in the Supabase SQL editor (Project -> SQL Editor). There is no
-- migration framework in this repo -- this matches how `documents` itself
-- was created.
--
-- One row per "matter" -- the same cluster key app/matters.py's
-- cluster_key() computes (sorted {client_name, counterparty_name} +
-- matter_type + jurisdiction). A partner can wall a matter so only emails
-- in allowed_emails can see its documents in search/library/lineage.

CREATE TABLE IF NOT EXISTS matter_walls (
    matter_key      text PRIMARY KEY,
    walled          boolean NOT NULL DEFAULT false,
    allowed_emails  text[] NOT NULL DEFAULT '{}',
    updated_by      text,
    updated_at      timestamptz NOT NULL DEFAULT now()
);
