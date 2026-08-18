# Precedent Bank — MVP

A working scaffold for *"turn a firm's messy documents into a trusted,
searchable precedent bank"* — built for The Lion's Pit 2026, Challenge 3.

Ingest messy files as-is → auto-tag them (no manual sorting) → browse or
search by practice area, or search for the exact clause you need instead
of a whole document → see exactly why each result ranked, was rejected, or
was blocked by an ethical wall → generate a draft with every clause
footnoted back to its source. A dedicated Start Here view curates the
firm's most-trusted precedents by practice area for anyone new to a team.

```
legal-precedent-bank/
├── backend/     FastAPI + Postgres/pgvector (Supabase) + OpenAI API
├── frontend/    React + Vite
└── README.md    you are here
```

## 1. Supabase setup (one-time)

The app uses a Supabase project for both the document store (Postgres +
pgvector) and login (Supabase Auth). From the Supabase dashboard:

1. **Run `backend/sql/matter_walls.sql` and `backend/sql/document_clauses.sql`**
   in the SQL Editor. (The `documents` table is expected to already exist
   — see `backend/app/vectorstore.py` for its shape if you're setting up
   a fresh project.)
2. **Authentication → Providers → Email**: turn off "Confirm email" so
   self-serve signup logs a user straight in — no email sending to set up
   for a hackathon demo.
3. Note down, from **Project Settings → API**: the Project URL and the
   anon/publishable key. You'll need these below (there's no need to touch
   JWT Settings at all — see the Login bullet under "How it works").

## 2. Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
```

Fill in `.env`:
- `OPENAI_API_KEY` — your real key.
- `DATABASE_URL` — Supabase Postgres connection string, "Transaction
  pooler" mode (Project Settings → Database).
- `SUPABASE_URL` / `SUPABASE_ANON_KEY` — from step 1.3 above (same values
  the frontend uses). Every route except `/api/health` returns 401
  without these set.
- `PARTNER_EMAILS` — comma-separated emails allowed to set/edit matter
  walls (e.g. your own, for testing).

Seed the demo corpus (17 deliberately messy sample documents — duplicate
versions, an outdated tenancy agreement, a partner-approved shareholders'
agreement, one filed under different terminology, a restricted settlement
memo, and a couple of irrelevant internal emails/memos to prove rejection
actually works):

```bash
python seed_demo_data.py --reset
```

This calls the LLM once per document to auto-tag it — that's the "low
-effort capture" step, not a canned fixture — and also splits each
document into individually-searchable clauses (no extra LLM call; see the
clause search bullet under "How it works"). Re-run any time you add more
files to `backend/demo_corpus/`.

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for interactive API docs (FastAPI's
built-in Swagger UI) — useful for demoing the API directly if you want to.

## 3. Frontend setup

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env
```

Fill in `.env`: `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` from step
1.3 above (`VITE_API_BASE_URL` can stay at its default unless your backend
runs somewhere other than `localhost:8000`).

```bash
npm run dev
```

Open `http://localhost:5173` — you'll land on a login screen. Sign up with
whatever email you put in `PARTNER_EMAILS` to get partner access (the
"Matters" tab and the ability to wall a matter).

## 4. Suggested demo flow

1. **Sign up / log in** — a plain email/password screen; no anonymous
   access to anything in the app.
2. **Start Here tab** — lands here by default. Shows what the tool does in
   a sentence each, the firm's most-relied-upon documents firm-wide, and
   every practice area with its top (partner-approved, most-used)
   precedents highlighted — this is the onboarding/continuity pillar made
   concrete: a new joiner doesn't need to already know where to look.
3. **Library tab** — show the corpus is genuinely messy (open a couple of
   the raw `.txt` files in `backend/demo_corpus/` first if you want the
   judges to see the "before"). Click **Ingest**, watch each file get read
   and auto-tagged live, with no manual sorting. Then use the practice
   area / jurisdiction / matter type / document type filters (plus the
   free-text box) to show browsing the corpus by facet, not just a flat
   list.
4. **Search & Draft tab, document mode** — run a query in plain English,
   e.g. *"cap on a shareholder's liability if they breach the agreement"*
   — this should surface the Alpha Robotics shareholders' agreements even
   though the query never says "indemnity" or "SHA".
5. Point out the **rejected** section: the outdated v1/v2 drafts get
   flagged with a plain-English reason (superseded, not partner-approved),
   not just silently dropped.
6. **Switch to clause mode** (toggle at the top of the search panel) and
   run something narrower, e.g. *"cap on indemnity liability"* — instead
   of ranking whole documents, this returns the exact clause, labeled and
   quoted, with a similarity score and a link back to its source document.
   This is the difference between "here's a 40-page agreement that's
   probably relevant" and "here's the paragraph you need."
7. **Matters tab** (partner account) — wall the Alpha Robotics matter,
   naming only a couple of allowed emails. Sign in as a different, unlisted
   account in a private window and re-run the same search (document or
   clause mode — both respect the wall) — the walled matter's documents
   disappear from search/library/lineage entirely and show up as "access
   restricted" instead. This is the ethical-wall / access-control pillar
   made real: it's tied to a verified login, not a toggle in the UI, and
   it's set per-matter by a partner, not inferred from a document.
8. Back on the partner account: select the top precedent(s), hit
   **Generate draft**, and click a citation badge in the draft — it
   scrolls to and highlights the exact source document above. This is the
   trust-building centerpiece: nothing in the draft is ungrounded, and
   anything the sources didn't cover shows up as a flagged gap instead of
   an invented clause.
9. Adjust a ranking weight slider (e.g. push "partner approval" up) and
   re-run the search to show a lawyer can tune what "best" means, live.

## How it works

- **Ingestion** (`backend/app/ingestion.py`): extracts text from
  `.txt` / `.docx` / `.pdf`, then asks the LLM to fill in a structured
  metadata schema (matter type, practice area, jurisdiction, industry,
  client type, transaction value, date, responsible lawyer, counterparty
  type, document type, completed/executed/draft-or-model status, version,
  partner approval, confidentiality, and a plain-English description).
- **Search** (`backend/app/search.py`): semantic search via Postgres +
  pgvector (OpenAI embeddings), then a transparent weighted score across
  similarity / recency / firm usage frequency / partner approval /
  jurisdiction match. Documents in the same rough "matter cluster" are
  compared against each other so an older or non-approved version can be
  flagged as superseded with a stated reason, rather than just silently
  ranked lower.
- **Login** (`backend/app/auth.py`, `frontend/src/supabaseClient.js`):
  Supabase Auth (email/password). Every API route except `/api/health`
  requires a verified session. The backend verifies each request's bearer
  token by asking Supabase's own Auth API (`GET /auth/v1/user`) whether
  it's valid, rather than decoding the JWT locally -- Supabase signs
  tokens with whichever algorithm a given project is configured for
  (legacy shared HS256 secret vs. newer asymmetric ES256 signing keys),
  so there's no one algorithm this backend can safely hardcode.
- **Ethical walls** (`backend/app/matters.py`): access control is
  matter-level, not per-document and not per-role — matching how this
  actually works at a firm (default access is open; a wall is the
  exception, applied to a specific matter by a partner, e.g. because of an
  adverse-client conflict). A "matter" is the same cluster key
  (`client_name` + `counterparty_name` + `matter_type` + `jurisdiction`)
  the search-ranking and lineage-graph logic already group documents by.
  Walling a matter sets an allow-list of emails; everyone else is blocked
  from that matter's documents in search, the library, lineage, and
  drafting alike — see `matters.is_blocked()`, the single check every one
  of those code paths goes through.
- **Drafting** (`backend/app/drafting.py`): the LLM drafts strictly from
  the selected source documents, inserting a `[[n]]` citation marker after
  every clause it draws on, and a `[[GAP: ...]]` marker instead of
  inventing anything the sources don't cover. The frontend renders `[[n]]`
  as clickable badges that jump back to the source.
- **Clause search** (`backend/app/ingestion.py:split_into_clauses`,
  `vectorstore.query_clauses`, `search.run_clause_search`): at ingest time,
  each document is split into individually-embedded "clauses" via a
  regex pass tuned to how legal documents actually number provisions
  ("1.", "Section 3:", "Clause 5.2", ...), falling back to paragraph
  chunking for unstructured text (emails, memos) rather than forcing a
  legal-clause shape onto something that doesn't have one. No LLM call
  for the split itself, so ingestion cost doesn't scale with how many
  clauses a document has. Toggle to "Search clauses" on the Search & Draft
  tab to rank individual provisions instead of whole documents — walled
  matters are blocked here exactly the same way as document search.
- **Faceted library browsing** (`frontend/src/components/DocumentLibrary.jsx`):
  filter the indexed corpus by practice area, jurisdiction, matter type,
  document type, or client type, plus free-text search — option lists are
  derived live from whatever's actually in the corpus, not a hardcoded
  taxonomy.
- **Start Here** (`frontend/src/components/StartHereView.jsx`): the
  onboarding/continuity pillar as a dedicated view, not just an implicit
  benefit of the precedent bank existing. Curates the firm's most-used
  documents firm-wide and, per practice area, the top partner-approved /
  most-used precedents — all computed client-side from the same
  wall-filtered `/api/documents` response every other view uses, so it
  never shows anyone a document they're not allowed to see.

## Deployment (Vercel)

`vercel.json` runs frontend and backend as two Vercel Services on one
domain (`/api/*` routes to the backend, everything else to the frontend),
so both share the same Supabase project as local dev. A few things that
are easy to miss and will produce a blank page or 401s if skipped:

- **The frontend needs its own `VITE_`-prefixed env vars in Vercel**,
  separate from the backend's. Vite bakes `VITE_SUPABASE_URL` /
  `VITE_SUPABASE_ANON_KEY` into the build at build time — the backend
  already having `SUPABASE_URL`/`SUPABASE_ANON_KEY` set (e.g. via
  Vercel's native Supabase integration) does **not** cover the frontend.
  Missing `VITE_` vars crash the whole page to blank before React even
  mounts (`supabaseClient.js` fails fast with a visible error card
  instead, as of the fix in this repo — but the underlying env vars still
  need to be set for login to actually work).
- **Env var changes need a redeploy to take effect** — saving a new value
  in the dashboard doesn't retroactively patch an already-built
  deployment. Use Deployments → **⋯** → **Redeploy**.
- **`PARTNER_EMAILS` isn't auto-provisioned** by the Supabase integration
  (unlike `SUPABASE_URL`/`SUPABASE_ANON_KEY`) — add it manually in
  Environment Variables or no one has partner access in production.
- If you ever run the backend test suite (`pytest`) against the same
  `DATABASE_URL` this deployment points at, know that it **resets and
  reseeds the real documents table** (`test_matter_walls.py`'s `setUp`
  calls `vectorstore.reset()`) — re-run `python seed_demo_data.py --reset`
  afterward, or point tests at a separate Supabase project.

## Extending this in the time you have left

- **More corpus**: drop more files into `backend/demo_corpus/` and re-run
  the seed script — the brief calls for 20–50 documents in the live demo.
- **Real conflict detection**: matter walls today are set by a partner by
  hand. A first pass at automatic conflict flagging is a name match across
  `client_name` / `counterparty_name` against existing matters at ingest
  time, surfaced to a partner as a suggestion rather than auto-applied.
- **Partner roles beyond an env var**: `PARTNER_EMAILS` in `backend/app/
  config.py` is a static allowlist — fine for a demo, but a real version
  would be a role stored per-user (e.g. in Supabase) with an admin screen
  to grant/revoke it.

## Notes

- No API keys or secrets are hardcoded anywhere. `backend/.env` and
  `frontend/.env` are both gitignored — only the `.env.example` files are
  committed.
- The vector store, matter/wall data, and auth all live in the same
  Supabase project. **Reset index** in the Library tab clears both the
  document store and all wall configuration, for a clean demo state.
