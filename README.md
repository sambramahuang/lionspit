# Precedent Bank — MVP

A working scaffold for *"turn a firm's messy documents into a trusted,
searchable precedent bank"* — built for The Lion's Pit 2026, Challenge 3.

Ingest messy files as-is → auto-tag them (no manual sorting) → search in
plain English or legal terms → see exactly why each result ranked, was
rejected, or was access-restricted → generate a draft with every clause
footnoted back to its source.

```
legal-precedent-bank/
├── backend/     FastAPI + ChromaDB + OpenAI API
├── frontend/    React + Vite
└── README.md    you are here
```

## 1. Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# open .env and paste in your real OPENAI_API_KEY
```

Seed the demo corpus (17 deliberately messy sample documents — duplicate
versions, an outdated tenancy agreement, a partner-approved shareholders'
agreement, one filed under different terminology, a restricted settlement
memo, and a couple of irrelevant internal emails/memos to prove rejection
actually works):

```bash
python seed_demo_data.py --reset
```

This calls the LLM once per document to auto-tag it — that's the "low
-effort capture" step, not a canned fixture. Re-run any time you add more
files to `backend/demo_corpus/`.

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for interactive API docs (FastAPI's
built-in Swagger UI) — useful for demoing the API directly if you want to.

## 2. Frontend setup

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env    # defaults to http://localhost:8000, edit if needed
npm run dev
```

Open `http://localhost:5173`.

## 3. Suggested demo flow

1. **Library tab** — show the corpus is genuinely messy (open a couple of
   the raw `.txt` files in `backend/demo_corpus/` first if you want the
   judges to see the "before"). Click **Ingest**, watch each file get read
   and auto-tagged live, with no manual sorting.
2. **Search & Draft tab** — run a query in plain English, e.g.
   *"cap on a shareholder's liability if they breach the agreement"* —
   this should surface the Alpha Robotics shareholders' agreements even
   though the query never says "indemnity" or "SHA".
3. Point out the **rejected** section: the outdated v1/v2 drafts get
   flagged with a plain-English reason (superseded, not partner-approved),
   not just silently dropped.
4. Toggle **viewer clearance** from standard to elevated and re-run the
   same query — the restricted settlement memo appears/disappears. This is
   the ethical-wall / access-control pillar made visible.
5. Select the top precedent(s), hit **Generate draft**, and click a
   citation badge in the draft — it scrolls to and highlights the exact
   source document above. This is the trust-building centerpiece: nothing
   in the draft is ungrounded, and anything the sources didn't cover shows
   up as a flagged gap instead of an invented clause.
6. Adjust a ranking weight slider (e.g. push "partner approval" up) and
   re-run the search to show a lawyer can tune what "best" means, live.

## How it works

- **Ingestion** (`backend/app/ingestion.py`): extracts text from
  `.txt` / `.docx` / `.pdf`, then asks the LLM to fill in a structured
  metadata schema (matter type, practice area, jurisdiction, industry,
  client type, transaction value, date, responsible lawyer, counterparty
  type, document type, completed/executed/draft-or-model status, version,
  partner approval, confidentiality, and a plain-English description).
- **Search** (`backend/app/search.py`): semantic search via ChromaDB
  (local embedding model, no extra API key needed), then a transparent
  weighted score across similarity / recency / firm usage frequency /
  partner approval / jurisdiction match. Documents in the same rough
  "matter cluster" are compared against each other so an older or
  non-approved version can be flagged as superseded with a stated reason,
  rather than just silently ranked lower.
- **Access control** (`backend/app/search.py`): documents tagged
  `confidentiality: restricted` are filtered out unless the request's
  `viewer_clearance` is `elevated` — a stand-in for a real permissions
  system, structured so it's a small extension to wire up to real auth
  later.
- **Drafting** (`backend/app/drafting.py`): the LLM drafts strictly from
  the selected source documents, inserting a `[[n]]` citation marker after
  every clause it draws on, and a `[[GAP: ...]]` marker instead of
  inventing anything the sources don't cover. The frontend renders `[[n]]`
  as clickable badges that jump back to the source.

## Extending this in the time you have left

- **More corpus**: drop more files into `backend/demo_corpus/` and re-run
  the seed script — the brief calls for 20–50 documents in the live demo.
- **Real auth**: `viewer_clearance` is currently a request field the
  frontend sets directly. Swapping it for a real per-user role is
  contained to `search.py` and the `/api/search` request.
- **Conflict detector**: the metadata schema already captures
  `client_type` / `counterparty_type` — a simple first pass is a name
  match across those fields at ingest time, flagged the same way
  `access_restricted` is now.
- **Document graph / lineage view**: `document_date` + `version` +
  the cluster grouping in `search.py` already contain what you'd need to
  render a precedent's version history as a small graph, if you want to
  build the map-style UI you discussed.

## Notes

- No API keys are hardcoded anywhere. `backend/.env` and `frontend/.env`
  are both gitignored — only the `.env.example` files are committed.
- The vector store is a local ChromaDB folder (`backend/chroma_data/`,
  gitignored). Delete it (or hit **Reset index** in the Library tab) to
  start clean.
- Chroma's local embedding model downloads once from Hugging Face on
  first run — make sure you have internet the first time you seed or
  ingest.
