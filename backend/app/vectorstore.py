"""
Postgres + pgvector vector store (Supabase). Replaces the earlier local
ChromaDB setup, which stored its index as a file on disk -- that worked
locally but not on Vercel, where the filesystem is read-only outside
/tmp and /tmp itself is wiped on every cold start, so every fresh
instance started with an empty, per-instance index. A real hosted
Postgres database is the same store for every user and every instance,
which is the actual requirement ("consistent documents for every user").

Embeddings come from OpenAI's API (text-embedding-3-small, 1536-dim)
rather than Chroma's bundled local model -- see llm_client.embed_text.
That's also serverless-friendly: it's just an HTTP call, no model
download/cache directory needed (no more HOME-redirect workaround).

A new connection is opened per call rather than a single cached one --
simpler and safer in a serverless context (no stale-connection-after-
cold-start class of bugs to worry about), and fast enough at this scale.
"""
import json

import psycopg
from pgvector.psycopg import register_vector

from app.config import settings
from app.llm_client import embed_text, embed_texts


def _connect():
    # prepare_threshold=None disables psycopg3's automatic server-side
    # prepared statements. DATABASE_URL points at Supabase's transaction
    # -mode pooler (pgbouncer/Supavisor), which can hand different client
    # calls the same underlying backend connection -- a prepared
    # statement name from one caller can collide with one already
    # registered by another, surfacing as "prepared statement ... already
    # exists". Simple (unprepared) queries avoid that entirely, which is
    # the standard fix when psycopg3 sits behind a transaction pooler.
    conn = psycopg.connect(settings.require_database_url(), prepare_threshold=None)
    register_vector(conn)
    return conn


def _clean_metadata(meta: dict) -> dict:
    """JSONB would happily store explicit nulls, but code throughout the
    app (e.g. `meta.get("client_name", "")`) assumes an *absent* key
    falls back to its default -- a stored null bypasses that fallback
    since the key technically exists (str(None) == "None", not ""). This
    matches the old Chroma vectorstore's behavior, which stripped None
    values before storage for the same reason."""
    return {k: v for k, v in meta.items() if v is not None}


def add_document(doc_id: str, text: str, metadata: dict):
    embedding = embed_text(text)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO documents (doc_id, text, metadata, embedding)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (doc_id) DO UPDATE
            SET text = EXCLUDED.text, metadata = EXCLUDED.metadata, embedding = EXCLUDED.embedding
            """,
            (doc_id, text, json.dumps(_clean_metadata(metadata)), embedding),
        )


def query(query_text: str, n_results: int = 8):
    """Shaped to match Chroma's old result format (nested single-query
    lists) so search.py's existing unpacking code needs no changes.
    pgvector's <=> operator is cosine distance, same convention Chroma
    used, so search.py's `1 - distance` similarity math still holds."""
    embedding = embed_text(query_text)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT doc_id, text, metadata, embedding <=> %s::vector AS distance
            FROM documents
            ORDER BY distance
            LIMIT %s
            """,
            (embedding, n_results),
        ).fetchall()

    if not rows:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    ids, docs, metas, distances = [], [], [], []
    for doc_id, text, metadata, distance in rows:
        ids.append(doc_id)
        docs.append(text)
        metas.append(metadata)
        distances.append(distance)
    return {"ids": [ids], "documents": [docs], "metadatas": [metas], "distances": [distances]}


def get_by_id(doc_id: str):
    with _connect() as conn:
        row = conn.execute(
            "SELECT doc_id, text, metadata FROM documents WHERE doc_id = %s",
            (doc_id,),
        ).fetchone()
    if not row:
        return None
    return {"doc_id": row[0], "text": row[1], "metadata": row[2]}


def list_all():
    with _connect() as conn:
        rows = conn.execute("SELECT doc_id, text, metadata FROM documents").fetchall()
    return [{"doc_id": r[0], "text": r[1], "metadata": r[2]} for r in rows]


def increment_usage(doc_id: str):
    """Bumps a document's usage_count -- feeds the 'frequency' ranking
    signal (how often the firm actually reaches for this precedent)."""
    with _connect() as conn:
        conn.execute(
            """
            UPDATE documents
            SET metadata = jsonb_set(
                metadata, '{usage_count}',
                to_jsonb(COALESCE((metadata->>'usage_count')::int, 0) + 1)
            )
            WHERE doc_id = %s
            """,
            (doc_id,),
        )


def reset():
    with _connect() as conn:
        # document_clauses FKs into documents -- both must be named in the
        # same TRUNCATE statement (or CASCADE used) or Postgres refuses.
        conn.execute("TRUNCATE TABLE document_clauses, documents")
        conn.execute("TRUNCATE TABLE matter_walls")
        conn.execute("TRUNCATE TABLE matter_conflict_flags")


def delete_document(doc_id: str):
    """Removes a single document (and its clauses, via ON DELETE CASCADE
    on document_clauses) without touching anything else in the index --
    the only way to correct a bad ingest short of a full reset()."""
    with _connect() as conn:
        conn.execute("DELETE FROM documents WHERE doc_id = %s", (doc_id,))


def add_document_clauses(doc_id: str, clauses: list[dict]):
    """Stores one row per {"label", "text"} clause (see
    ingestion.split_into_clauses) with its own embedding, replacing any
    existing clauses for this doc_id -- so re-ingesting a doc_id (the
    ON CONFLICT path in add_document) doesn't leave stale clause rows
    behind alongside the fresh ones."""
    if not clauses:
        return
    embeddings = embed_texts([c["text"] for c in clauses])
    with _connect() as conn:
        conn.execute("DELETE FROM document_clauses WHERE doc_id = %s", (doc_id,))
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO document_clauses (doc_id, clause_index, label, text, embedding)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (doc_id, i, c["label"], c["text"], emb)
                    for i, (c, emb) in enumerate(zip(clauses, embeddings))
                ],
            )


def query_clauses(query_text: str, n_results: int = 15):
    """Same nested-list result shape as query(), plus clause_index/label,
    so search.py's candidate-building code can treat clause and document
    search the same way."""
    embedding = embed_text(query_text)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT dc.doc_id, dc.clause_index, dc.label, dc.text, d.metadata,
                   dc.embedding <=> %s::vector AS distance
            FROM document_clauses dc
            JOIN documents d ON d.doc_id = dc.doc_id
            ORDER BY distance
            LIMIT %s
            """,
            (embedding, n_results),
        ).fetchall()
    return [
        {
            "doc_id": r[0],
            "clause_index": r[1],
            "label": r[2],
            "text": r[3],
            "meta": r[4],
            "similarity": max(0.0, min(1.0, 1 - r[5])),
        }
        for r in rows
    ]


def get_wall(matter_key: str):
    with _connect() as conn:
        row = conn.execute(
            "SELECT matter_key, walled, allowed_emails, updated_by, updated_at "
            "FROM matter_walls WHERE matter_key = %s",
            (matter_key,),
        ).fetchone()
    return _wall_row_to_dict(row) if row else None


def list_walls() -> dict:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT matter_key, walled, allowed_emails, updated_by, updated_at FROM matter_walls"
        ).fetchall()
    return {row[0]: _wall_row_to_dict(row) for row in rows}


def set_wall(matter_key: str, walled: bool, allowed_emails: list[str], updated_by: str) -> dict:
    with _connect() as conn:
        row = conn.execute(
            """
            INSERT INTO matter_walls (matter_key, walled, allowed_emails, updated_by, updated_at)
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (matter_key) DO UPDATE
            SET walled = EXCLUDED.walled,
                allowed_emails = EXCLUDED.allowed_emails,
                updated_by = EXCLUDED.updated_by,
                updated_at = now()
            RETURNING matter_key, walled, allowed_emails, updated_by, updated_at
            """,
            (matter_key, walled, allowed_emails, updated_by),
        ).fetchone()
    return _wall_row_to_dict(row)


def _wall_row_to_dict(row) -> dict:
    return {
        "matter_key": row[0],
        "walled": row[1],
        "allowed_emails": row[2] or [],
        "updated_by": row[3],
        "updated_at": row[4].isoformat() if row[4] else None,
    }


def flag_conflict(matter_key: str, reason: str, flagged_doc_id: str):
    """Upserts a conflict flag for a matter -- re-detecting a conflict for
    an already-flagged matter refreshes the reason and resets it to
    unacknowledged, since a fresh signal deserves a fresh look even if a
    prior one was dismissed."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO matter_conflict_flags (matter_key, reason, flagged_doc_id, detected_at, acknowledged)
            VALUES (%s, %s, %s, now(), false)
            ON CONFLICT (matter_key) DO UPDATE
            SET reason = EXCLUDED.reason,
                flagged_doc_id = EXCLUDED.flagged_doc_id,
                detected_at = now(),
                acknowledged = false,
                acknowledged_by = NULL,
                acknowledged_at = NULL
            """,
            (matter_key, reason, flagged_doc_id),
        )


def list_conflicts() -> dict:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT matter_key, reason, flagged_doc_id, detected_at, acknowledged, acknowledged_by, acknowledged_at "
            "FROM matter_conflict_flags"
        ).fetchall()
    return {row[0]: _conflict_row_to_dict(row) for row in rows}


def acknowledge_conflict(matter_key: str, acknowledged_by: str):
    with _connect() as conn:
        row = conn.execute(
            """
            UPDATE matter_conflict_flags
            SET acknowledged = true, acknowledged_by = %s, acknowledged_at = now()
            WHERE matter_key = %s
            RETURNING matter_key, reason, flagged_doc_id, detected_at, acknowledged, acknowledged_by, acknowledged_at
            """,
            (acknowledged_by, matter_key),
        ).fetchone()
    return _conflict_row_to_dict(row) if row else None


def _conflict_row_to_dict(row) -> dict:
    return {
        "matter_key": row[0],
        "reason": row[1],
        "flagged_doc_id": row[2],
        "detected_at": row[3].isoformat() if row[3] else None,
        "acknowledged": row[4],
        "acknowledged_by": row[5],
        "acknowledged_at": row[6].isoformat() if row[6] else None,
    }
