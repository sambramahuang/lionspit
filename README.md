# Kitsu — Precedent Bank MVP

A working scaffold for *"turn a firm's messy documents into a trusted,
searchable precedent bank"* — built for The Lion's Pit 2026, Challenge 3.

Ingest messy files as-is → auto-tag them (no manual sorting) → browse or
search by practice area, or search for the exact clause you need instead
of a whole document → see exactly why each result ranked, was rejected, or
was blocked by an ethical wall → generate a draft with every clause
footnoted back to its source, editable in place and exportable to
.docx/.pdf/.txt. A dedicated Start Here view curates the firm's most
-trusted precedents by practice area for anyone new to a team, and a
lineage graph maps every matter's version history at a glance.

```
lionspit/
├── backend/          FastAPI + Postgres/pgvector (Supabase) + OpenAI API
├── frontend/          React + Vite ("Kitsu")
├── case_documents/    seed corpus — 104 files across 20 matters
└── README.md          you are here
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
- `OPENAI_API_KEY` — your real key. Used for metadata extraction, chat
  completions (drafting), embeddings, and vision transcription (OCR — see
  below).
- `OPENAI_MODEL` / `OPENAI_EMBEDDING_MODEL` — default to `gpt-4o-mini` and
  `text-embedding-3-small`; only change if you know you want to.
- `DATABASE_URL` — Supabase Postgres connection string, "Transaction
  pooler" mode (Project Settings → Database).
- `SUPABASE_URL` / `SUPABASE_ANON_KEY` — from step 1.3 above (same values
  the frontend uses). Every route except `/api/health` returns 401
  without these set.
- `PARTNER_EMAILS` — comma-separated emails allowed to set/edit matter
  walls, approve precedents, acknowledge conflicts, and delete
  documents/matters (e.g. your own, for testing).

Seed the demo corpus — `case_documents/` at the repo root, 104 real
`.docx`/`.pdf`/`.txt` files across 20 matters, spanning four sub-sets: a
litigation set (two Singapore High Court disputes, each with an
application for specific production of documents, plus three
transactional matters — a residential conveyancing, a Series B
shareholders' agreement, and a Vietnam trademark licence); a
corporate/transactional set purpose-built around version discrimination,
supersession, semantic-vs-lexical matching, access control and conflicts
(a two-party joint venture shareholders' agreement, a Series A financing,
a superseded 2024 precedent, a tenancy, and an employment matter); a
second fictional firm's "Northstar & Vale" set (an asset acquisition, an
energy dispute, a second venture financing, and a data-breach matter) that
rounds out practice-area coverage and supplies a second, independent
conflict example; and a services & distributorship set (contributed by
Trisha) that forces the system to work out which side of a deal each
document was drafted for, catch a same-substance/different-vocabulary
semantic trap, and OCR a genuinely image-only scanned exhibit. Every
matter carries client correspondence on firm letterhead, a billing
summary, a draft with genuine partner mark-up (struck-through deletions,
underlined insertions, marginal reviewer comments), a redlined/negotiated
version, a final/executed version, and at least one same-matter "noise"
document that shouldn't surface for an unrelated query. See
`case_documents/README.md` for the full per-matter breakdown and ground
truth:

```bash
python seed_demo_data.py --reset
```

This walks every file under `case_documents/` (all four sub-sets at once)
and calls the LLM once per document to auto-tag it — that's the "low
-effort capture" step, not a canned fixture — and also splits each
document into individually-searchable clauses (no extra LLM call; see the
clause search bullet under "How it works"). Re-run any time you add more
files under `case_documents/`.

Two smaller scripts exist alongside it for incremental, non-destructive
re-ingestion into an already-seeded store (they skip any filename already
indexed, so they're safe to re-run): `ingest_generated_data.py` (the
Northstar & Vale set, with its matter facts pinned so the conflict
relationships stay deterministic) and `ingest_trisha_data.py` (the
services & distributorship set). `retag_metadata.py` re-runs metadata
extraction against everything already indexed, in place, without
re-uploading or resetting — useful after a change to the metadata schema
(e.g. the `document_type` category list) so older documents don't fall out
of a filter that only matches the current category values.

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
whatever email you put in `PARTNER_EMAILS` to get partner access (matter
walls, precedent approval, conflict acknowledgment, and document/matter
deletion).

## 4. Suggested demo flow

1. **Sign up / log in** — a plain email/password screen; no anonymous
   access to anything in the app. First sign-in lands on a "Welcome to
   Kitsu" screen; click **Start Here** (or the Home icon in the dock at any
   time) to reach the full overview.
2. **Home tab, Start Here overview** — a bento grid explains what the tool
   does in a sentence each (plain-English search, clause search, ethical
   walls, transparent reasoning, version lineage, cited drafting), then
   shows the firm's most-relied-upon documents firm-wide and every
   practice area with its top (partner-approved, most-used) precedents
   highlighted — this is the onboarding/continuity pillar made concrete: a
   new joiner doesn't need to already know where to look.
3. **Library tab** — show the corpus is genuinely messy (open a couple of
   the raw files in `case_documents/` first if you want the judges to see
   the "before" — a redlined `.docx` with visible strikethrough/underline
   mark-up and a printed-email `.pdf` on firm letterhead both make the
   point better than a plain `.txt` would). The corpus is already indexed
   via the seed script; use the practice area / jurisdiction / matter type
   / document type / client type / document status filters (plus the
   free-text box) to show browsing it by facet, not just a flat list of
   documents. Click **Preview** on any row to open the inline document
   preview (same modal used everywhere else a document can be previewed —
   search results, lineage, Start Here). Live ingestion itself gets its
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
7. **Library tab → Matters view** (the view-toggle at the top of Library:
   List view / Lineage graph / Matters — partner account) — wall the
   Meridian Robotics v Vantage Components matter, naming only a couple of
   allowed emails. Sign in as a different, unlisted account in a private
   window and re-run the same search (document or clause mode — both
   respect the wall) — the walled matter's documents disappear from
   search/library/lineage entirely and show up as "access restricted"
   instead. This is the ethical-wall / access-control pillar made real:
   it's tied to a verified login, not a toggle in the UI, and it's set
   per-matter by a partner, not inferred from a document.
8. Back on the partner account: select the two final specific-production
   submissions, hit **Generate draft** for a similar application, and
   click a citation badge in the draft — it scrolls to and highlights the
   exact source document above. The draft itself is editable in place
   (citation, gap, and uncited badges stay locked so an edit can't
   silently corrupt the citation trail) and exportable as .txt, .docx, or
   .pdf, with a Sources/Gaps appendix appended automatically. This is the
   trust-building centerpiece: nothing in the draft is ungrounded, and
   anything the sources didn't cover shows up as a flagged gap instead of
   an invented clause.
9. Open **Filters & weights** in the search panel and adjust a ranking
   weight slider (e.g. push "partner approval" up) and re-run the search
   to show a lawyer can tune what "best" means, live. Also point out
   **Attach a document for context** — a lawyer can attach their own case
   file (extracted client-side, never indexed into the library) as one-off
   extra search context without permanently adding it to the corpus.
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
    highlighted row for a partner to **acknowledge**. Nothing gets walled
    automatically — a partner still makes the call.
11. **Delete a document** (partner account) — in the Library tab, delete
    one of the same-matter noise documents (e.g. the unrelated
    charterparty redline in the Harborview Shipping matter) instead of
    wiping the whole index. The **Lineage graph** and **Matters** views
    also expose a **Delete matter** action for cascading through every
    document in a matter at once. Sign in as a non-partner and confirm
    none of the delete/approve/wall controls are there at all.
12. **Approve a precedent** (partner account) — in the Library tab, mark a
    document partner-approved (or revoke it). Approval feeds directly into
    search ranking (the "partner approval" weight) and into what Start
    Here curates as the firm's top precedent per practice area — this is
    how a partner's judgment becomes the system's judgment, not a separate
    disconnected feature.

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
  both the metadata LLM and the embeddings. A PDF whose extracted text
  comes back near-empty (a scanned document, not a native PDF) falls back
  to OCR: each page is rendered to an image via PyMuPDF and transcribed
  with a vision model, capped at a fixed page count so one large scan
  doesn't turn a single upload into dozens of vision calls — a vision-API
  outage degrades to today's "no extractable text" failure instead of
  blocking ingestion on it.
- **Search** (`backend/app/search.py`): semantic search via Postgres +
  pgvector (OpenAI embeddings), then a transparent weighted score across
  similarity / recency / firm usage frequency / partner approval /
  jurisdiction match — all five weights are user-tunable sliders in the
  Search & Draft panel, not fixed constants. Documents in the same rough
  "matter cluster" are compared against each other so an older or non
  -approved version can be flagged as superseded with a stated reason,
  rather than just silently ranked lower. Jurisdiction, matter type,
  recency, document type, and draft/model/executed status are all
  optional filters on top of the ranked results. A lawyer can also attach
  their own document as one-off extra query context (via `/api/extract
  -text`, which extracts text the same way ingestion does but never
  touches the vector store) without it becoming a permanent, browsable
  precedent.
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
  paths goes through. A walled document still *appears* in `/api/documents`
  (existence isn't hidden, only content is) so a lawyer can see a matter
  exists and is restricted rather than have it silently vanish.
- **Drafting** (`backend/app/drafting.py`): the LLM drafts strictly from
  the selected source documents, inserting a `[[n]]` citation marker after
  every clause it draws on, and a `[[GAP: ...]]` marker instead of
  inventing anything the sources don't cover; a clause the model wrote
  with neither marker is caught and flagged `[[UNCITED]]` rather than
  silently passing as grounded. The frontend (`DraftView.jsx`) renders
  `[[n]]` as clickable badges that jump back to the source, and the whole
  draft is editable in place in a contentEditable surface — citation/gap
  /uncited tokens are locked (`contenteditable="false"`) so editing the
  surrounding prose can't accidentally type through one and corrupt the
  citation trail. `frontend/src/utils/draftExport.js` reads the live
  -edited DOM (not the original AI output) back into structured paragraphs
  and exports what's actually on screen as `.txt`, `.docx` (via the
  `docx` package), or `.pdf` (via `jspdf`), each with a Sources/Gaps
  /Uncited appendix appended automatically; both libraries are dynamically
  imported only when an export button is actually clicked.
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
  matters are blocked here exactly the same way as document search, and
  matching clauses can be selected straight into a draft.
- **Document preview** (`frontend/src/components/PreviewModal.jsx`,
  `frontend/src/hooks/useDocumentPreview.js`): one shared modal and fetch
  -state hook used everywhere a document can be opened — search results,
  the library table, the lineage graph, Start Here — so there's a single
  implementation instead of one per screen. Renders the extracted text
  with light structure recovery (a bordered key/value strip for a
  document's own header fields, a centered heading for a letterhead/
  section title, justified paragraphs elsewhere with numbered clause leads
  bolded) purely for readability; it never changes what text is shown.
- **Faceted library browsing** (`frontend/src/components/DocumentLibrary.jsx`):
  filter the indexed corpus by practice area, jurisdiction, matter type,
  document type, client type, or document status (draft / model / executed
  / unknown), plus free-text search — option lists are derived live from
  whatever's actually in the corpus, not a hardcoded taxonomy.
- **Version lineage** (`backend/app/search.py:compute_lineage`,
  `frontend/src/components/LineageGraph.jsx`): a corpus-wide version
  -history graph, one cluster per matter, computed from the same matter
  -clustering and supersession logic search ranking uses. The current
  document sits at the hub of a left-to-right version chain (draft →
  redlined → final, etc.); every other same-matter document (correspondence,
  billing, file notes) fans into it on a dashed "related" edge instead of
  being treated as a version step. Each edge carries the same plain
  -English reason shown in search's rejected/superseded section. Partners
  can delete an entire matter from here in one action.
- **Start Here** (`frontend/src/components/HeroView.jsx`,
  `OverviewView.jsx`, `BentoGrid.jsx`): the onboarding/continuity pillar as
  a dedicated Home tab, not just an implicit benefit of the precedent bank
  existing. A welcome screen introduces the tool; the overview beneath it
  curates the firm's most-used documents firm-wide and, per practice area,
  the top partner-approved / most-used precedents — all computed
  client-side from the same wall-filtered `/api/documents` response every
  other view uses, so it never shows anyone a document they're not
  allowed to see.
- **Partner approval** (`POST /api/documents/{doc_id}/approval`,
  `vectorstore.set_document_approval`): a partner can mark a document
  partner-approved (optionally with a note) or revoke that mark, wall
  -checked the same way every other document-mutating route is. This is
  the human judgment call that feeds the "partner approval" ranking weight
  and Start Here's trust ordering — the system never infers approval on
  its own.
- **Automatic conflict detection** (`backend/app/conflicts.py`): at ingest
  time, the new document's `client_name`/`counterparty_name` are checked
  against every *other* matter's for the classic positional-conflict
  pattern — the new matter's party appears on the opposite side of an
  existing, unrelated matter, meaning the firm may now be adverse to an
  existing client (or representing someone it was previously adverse to).
  Deliberately scans across ethical walls (a wall hiding a matter from one
  lawyer must not also hide it from the conflict check, or the two
  features would defeat each other) and deliberately never auto-applies a
  wall — a flag surfaces on the Matters view (`matter_conflict_flags`
  table) for a partner to review and `POST
  /api/matters/{matter_key}/conflict/acknowledge`. Acknowledging doesn't
  delete the flag record, just clears its unresolved state, and a fresh
  detection later resets it — so acknowledging today doesn't silence a
  genuinely new signal tomorrow. Case-insensitive exact name matching only
  (`conflicts._name`) — unlike matter clustering (`matters.cluster_key`),
  which now tolerates entity-suffix formatting differences, this still
  won't recognize "Vantage Components Pte Ltd" and "Vantage Components" as
  the same company (see "Extending this" below).
- **Document and matter deletion** (`DELETE /api/documents/{doc_id}`,
  `DELETE /api/matters/{matter_key}`): removing a single wrongly-ingested
  or genuinely obsolete document used to mean wiping the entire index —
  the single-document route is the fix for that. The matter route cascades
  through every document whose computed cluster key matches, for cleaning
  out an entire bad or duplicate matter at once (available from both the
  Matters view and the Lineage graph). Both are partner-gated like wall
  edits (they mutate a corpus every lawyer relies on) and wall-checked the
  same way every other document-returning route is — a partner personally
  walled off a matter still can't act on documents inside it.

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

## Tests

```bash
cd backend
pytest
```

`backend/tests/` covers matter walls (`test_matter_walls.py`), automatic
conflict detection (`test_conflicts.py`), clause search
(`test_clause_search.py`), document deletion
(`test_document_delete.py`), and document preview
(`test_document_preview.py`), against `auth_helpers.py`'s shared fake
-auth fixtures. As noted above, these tests call `vectorstore.reset()` —
never point them at a database you care about keeping seeded.

## Extending this in the time you have left

- **More corpus**: drop more files into `case_documents/` (any client
  subfolder, or a new one) and re-run the seed script — currently 104
  documents across 20 matters, but more matters means richer
  clustering/lineage/conflict demos.
- **Conflict detection beyond exact-name matching**: today's check
  (`backend/app/conflicts.py`) is still case-insensitive exact matching
  only — fuzzy/alias matching (e.g. "Vantage Components" vs "Vantage
  Components Pte Ltd") would catch more real conflicts. Matter clustering
  (`matters.cluster_key`) already got this treatment (entity-suffix
  normalization, plus a content-based fallback for documents with no
  usable name at all — see "Ethical walls" above); the same normalization
  helper (`matters._normalize_party_name`) would be a reasonable starting
  point for `conflicts.py` too.
- **Partner roles beyond an env var**: `PARTNER_EMAILS` in `backend/app/
  config.py` is a static allowlist — fine for a demo, but a real version
  would be a role stored per-user (e.g. in Supabase) with an admin screen
  to grant/revoke it.
- **Metadata editing**: a wrong auto-tag (bad date, missed version) has no
  general fix today short of deleting and re-ingesting — partner approval
  and `retag_metadata.py` cover two specific cases (marking a document
  trusted, and refreshing everyone's tags after a schema change), but
  there's still no UI to hand-correct one field on one document.

## Notes

- No API keys or secrets are hardcoded anywhere. `backend/.env` and
  `frontend/.env` are both gitignored — only the `.env.example` files are
  committed.
- The vector store, matter/wall data, and auth all live in the same
  Supabase project. **Reset index** in the Library tab clears the document
  store (documents and clauses), all wall configuration, and all conflict
  flags, for a clean demo state.
