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

1. **Run `backend/sql/matter_walls.sql`, `backend/sql/document_clauses.sql`,
   and `backend/sql/matter_conflicts.sql`** in the SQL Editor. (The
   `documents` table is expected to already exist — see `backend/app/
   vectorstore.py` for its shape if you're setting up a fresh project.)
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

Seed the demo corpus — `case_documents/` at the repo root, 76 real
`.docx`/`.pdf`/`.txt` files across 14 matters, spanning three sub-sets: two
Singapore High Court disputes (each with an application for specific
production of documents) plus three transactional matters (a residential
conveyancing, a Series B shareholders' agreement, and a Vietnam trademark
licence); a companion corporate/transactional set purpose-built around
version discrimination, supersession, semantic-vs-lexical matching, access
control and conflicts (a two-party joint venture shareholders' agreement,
a Series A financing, a superseded 2024 precedent, a tenancy, and an
employment matter); and a second fictional firm's four matters (an asset
acquisition, an energy dispute, a second venture financing, and a data
-breach matter) that round out practice-area coverage and supply a second,
independent conflict example. Every matter carries client correspondence
on firm letterhead, a billing summary, a draft with genuine partner
mark-up (struck-through deletions, underlined insertions, marginal
reviewer comments), a redlined/negotiated version, a final/executed
version, and at least one same-matter "noise" document that shouldn't
surface for an unrelated query. See `case_documents/README.md` for the
full per-matter breakdown and ground truth:

```bash
python seed_demo_data.py --reset
```

This calls the LLM once per document to auto-tag it — that's the "low
-effort capture" step, not a canned fixture — and also splits each
document into individually-searchable clauses (no extra LLM call; see the
clause search bullet under "How it works"). Re-run any time you add more
files under `case_documents/`.

Deliberately **not** seeded: `backend/live_ingest_demo/`, a single
new-client intake memo held back so you can ingest it live through the
Library tab's Ingest button during the demo (step 10 below) and watch the
conflict flag appear in real time, rather than it already being in the
index when the demo starts.

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
   the raw files in `case_documents/` first if you want the judges to see
   the "before" — a redlined `.docx` with visible strikethrough/underline
   mark-up and a printed-email `.pdf` on firm letterhead both make the
   point better than a plain `.txt` would). The corpus is already indexed
   via the seed script; use the practice area / jurisdiction / matter type
   / document type filters (plus the free-text box) to show browsing it by
   facet, not just a flat list of 30 files. Live ingestion itself gets its
   own dedicated moment in step 10.
4. **Search & Draft tab, document mode** — run the query
   `case_documents/README.md` was itself built around: *"Draft a legal
   argument in IRAC for a request for specific production under the Rules
   of Court 2021."* This should surface the specific-production
   submissions from **both** litigation matters (Meridian Robotics v
   Vantage Components; Harborview Shipping v Straits Bunker Supplies) —
   even though the query never names either party — and should **not**
   surface anything from the three transactional matters, nor the
   same-matter noise documents (the unrelated charterparty redline, the
   unrelated draft supply agreement with a replacement vendor).
5. Point out the **rejected** section: each litigation matter's
   `03_draft_submission...` — circulated for partner review, still under
   mark-up, not yet filed — gets flagged with a plain-English reason
   (superseded by the later, partner-approved `04_final_submission...`)
   instead of silently dropped. This is a genuinely harder draft-vs-final
   call than a document that just says "DRAFT" at the top, since the
   draft's substance is largely the same text before the partner's edits.
6. **Switch to clause mode** (toggle at the top of the search panel) and
   run something narrower, e.g. *"the threshold for specific production
   under Order 11 Rule 3"* — instead of ranking whole documents, this
   returns the exact paragraph, labeled and quoted, with a similarity
   score and a link back to its source document. This is the difference
   between "here's a 15-page submission that's probably relevant" and
   "here's the paragraph you need."
7. **Library tab → Matters view** (partner account) — wall the Meridian
   Robotics v Vantage Components matter, naming only a couple of allowed
   emails. Sign in as a different, unlisted account in a private window and
   re-run the
   same search (document or clause mode — both respect the wall) — the
   walled matter's documents disappear from search/library/lineage
   entirely and show up as "access restricted" instead. This is the
   ethical-wall / access-control pillar made real: it's tied to a verified
   login, not a toggle in the UI, and it's set per-matter by a partner, not
   inferred from a document.
8. Back on the partner account: select the two final specific-production
   submissions, hit **Generate draft** for a similar application, and
   click a citation badge in the draft — it scrolls to and highlights the
   exact source document above. This is the trust-building centerpiece:
   nothing in the draft is ungrounded, and anything the sources didn't
   cover shows up as a flagged gap instead of an invented clause.
9. Adjust a ranking weight slider (e.g. push "partner approval" up) and
   re-run the search to show a lawyer can tune what "best" means, live.
10. **Automatic conflict detection** — in the Library tab, click
    **Ingest** and pick `backend/live_ingest_demo
    /new_client_intake_vantage_components.txt`: a new-client intake memo
    for "Vantage Components Pte Ltd" — the same company already on record
    as the *counterparty* being sued in the Meridian Robotics matter. Its
    own intake memo says the manual conflict check came up clean (searched
    for "Vantage Components", found nothing — a plausible miss, since nothing
    in a name search would connect it to a suit filed under "Meridian
    Robotics v Vantage Components"). The automatic check has no such blind
    spot: it compares the new document's `client_name` against every other
    matter's `client_name`/`counterparty_name` directly, flags the match
    immediately in the ingest result with a plain-English reason, and it
    shows up in the **Matters view** (still on the Library tab) as a
    highlighted row for a partner to acknowledge — switching there after the
    ingest shows it immediately, no separate tab or manual refresh needed.
    Nothing gets walled automatically — a partner still makes the call.
11. **Delete a document** (partner account) — in the Library tab, delete
    one of the same-matter noise documents (e.g. the unrelated
    charterparty redline in the Harborview Shipping matter) instead of
    wiping the whole index. Sign in as a non-partner and confirm the
    Delete button isn't there at all.

## How it works

- **Ingestion** (`backend/app/ingestion.py`): extracts text from
  `.txt` / `.docx` / `.pdf`, then asks the LLM to fill in a structured
  metadata schema (matter reference number if the document states one,
  matter type, practice area, jurisdiction, industry, client type,
  transaction value, date, responsible lawyer, counterparty type, document
  type, completed/executed/draft-or-model status, version, partner
  approval, confidentiality, and a plain-English description).
  `.docx` extraction deliberately skips struck-through runs: real redlines
  are usually manual strikethrough/underline character formatting rather
  than actual Word tracked-changes XML, so a naive paragraph-text read
  concatenates the "deleted" and "inserted" text back-to-back with no
  separator (e.g. "12 weeks10 weeks") — dropping the struck-through half
  recovers the clean, current reading instead of feeding garbled text to
  both the metadata LLM and the embeddings.
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
  (`matters.cluster_key`) the search-ranking and lineage-graph logic
  already group documents by: the explicit matter/case reference number a
  document cites (e.g. "HC/S 214/2026"), when it cites one, since a real
  case file mixes document types (correspondence, billing, drafts, a final
  version, internal memos) that the metadata LLM can reasonably tag with
  different matter_type/practice_area guesses despite being unambiguously
  the same file — an explicit reference number is a stronger, type-agnostic
  signal than any inferred combination of fields. Falls back to the
  *unordered set* of `client_name` + `counterparty_name` plus `matter_type`
  + `jurisdiction` when no reference is stated — party names are compared
  entity-suffix-insensitively (`matters._normalize_party_name`), so "Alpha
  Robotics Pte Ltd" and a document that just says "Alpha Robotics" still
  count as the same party. For the rare document with neither a reference
  number nor a usable party name — a genuinely messy upload — search
  ranking and the lineage graph fall back one step further to
  `matters.resolve_cluster_keys`, which compares the document's embedding
  against the rest of the corpus and merges it into whichever existing
  matter it's a near-duplicate of, so a matter isn't permanently fractured
  just because one file's metadata extraction came back empty. This
  content-based fallback deliberately isn't used by `is_blocked()` itself —
  wall enforcement always stays on the plain structural key, so a fuzzy
  content match can never change what a document is judged to be for
  access-control purposes, only for grouping in search/lineage. Walling a
  matter sets an allow-list of emails; everyone else is blocked from that
  matter's documents in search, the library, lineage, and drafting alike —
  see `matters.is_blocked()`, the single check every one of those code
  paths goes through.
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
- **Automatic conflict detection** (`backend/app/conflicts.py`): at ingest
  time, the new document's `client_name`/`counterparty_name` are checked
  against every *other* matter's for the classic positional-conflict
  pattern — the new matter's party appears on the opposite side of an
  existing, unrelated matter, meaning the firm may now be adverse to an
  existing client (or representing someone it was previously adverse to).
  Deliberately scans across ethical walls (a wall hiding a matter from one
  lawyer must not also hide it from the conflict check, or the two
  features would defeat each other) and deliberately never auto-applies a
  wall — a flag surfaces on the Matters page (`matter_conflict_flags`
  table) for a partner to review and acknowledge. First-pass name matching
  only, same limitation as matter clustering: "Vantage Components Pte Ltd"
  and "Vantage Components" won't be recognized as the same company.
- **Document deletion** (`DELETE /api/documents/{doc_id}`): removing a
  single wrongly-ingested or genuinely obsolete document used to mean
  wiping the entire index — this is the actual fix. Partner-gated like
  wall edits (it mutates a corpus every lawyer relies on), and wall
  -checked the same way every document-returning route is.

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

- **More corpus**: drop more files into `case_documents/` (any client
  subfolder, or a new one) and re-run the seed script — currently 76
  documents across 14 matters, but more matters means richer
  clustering/lineage/conflict demos.
- **Conflict detection beyond exact-name matching**: today's check
  (`backend/app/conflicts.py`) is case-insensitive exact matching only —
  fuzzy/alias matching (e.g. "Vantage Components" vs "Vantage Components
  Pte Ltd") would catch more real conflicts.
- **Partner roles beyond an env var**: `PARTNER_EMAILS` in `backend/app/
  config.py` is a static allowlist — fine for a demo, but a real version
  would be a role stored per-user (e.g. in Supabase) with an admin screen
  to grant/revoke it.
- **Metadata editing**: a wrong auto-tag (bad date, missed version) has no
  fix today short of deleting and re-ingesting — there's no metadata-edit
  UI, only the new per-document delete.

## Notes

- No API keys or secrets are hardcoded anywhere. `backend/.env` and
  `frontend/.env` are both gitignored — only the `.env.example` files are
  committed.
- The vector store, matter/wall data, and auth all live in the same
  Supabase project. **Reset index** in the Library tab clears both the
  document store and all wall configuration, for a clean demo state.
