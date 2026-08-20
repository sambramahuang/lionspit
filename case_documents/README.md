# Synthetic Law Firm Document Repository — Hackathon Demo Dataset

All matters, parties, firms, and individuals below are **entirely fictional**,
created for demonstrating a document-classification/retrieval solution.
Do not use any names or facts herein as real precedent or real party data.

## Purpose
This repository simulates two small Singapore law firms' flat, client-name-
based folder structures (no case management system) — mixed document types,
some relevant to a given query and some irrelevant "noise", exactly as
they'd sit in a real shared drive. It combines three sub-sets, seeded
together and searched as one corpus:

- **Litigation set** (`HC-S-214-2026`, `HC-ADM-88-2026`, `MAT-2026-0398`,
  `MAT-2026-0455`, `MAT-2026-0512`) — Goh Legal Partners / Ho & Partners /
  Nathan Law / Wee Corporate Law / Ang IP, testing retrieval against a
  **specific-production litigation** prompt.
- **Corporate/transactional set** (`MAT-2024-0912`, `MAT-2026-0473`,
  `MAT-2026-0508`, `MAT-2026-0530`, `MAT-2026-0561`) — Wee Corporate Law
  LLC, testing retrieval against a **shareholders-agreement drafting**
  prompt, and purpose-built to exercise version discrimination, supersession,
  vocabulary mismatch, access control, and conflicts (see below).
- **Northstar & Vale set** (`MAT-2026-0601`–`MAT-2026-0604`) — a second
  fictional firm, plain-text matters that round out practice-area coverage
  (M&A asset purchase, energy dispute, venture financing, data breach) and
  supply a second, independent example of the automatic conflict check: the
  same party (Meridian Infrastructure Holdings) appears as the *counterparty*
  in `MAT-2026-0601` and then as the *client* in `MAT-2026-0602`.

Folders are named by **court suit/summons number** (for litigation matters)
or **internal firm matter reference number** (for transactional matters) —
never by client name — matching how a small firm's shared drive is actually
organised.

## Ground truth — litigation set

| Folder | Matter | Involves an application for **specific production**? |
|---|---|---|
| `HC-S-214-2026` | Meridian Robotics Pte Ltd v Vantage Components Pte Ltd | **YES** — breach of supply contract; application for specific production of QA/defect logs (Summons HC/SUM 611/2026) |
| `HC-ADM-88-2026` | Harborview Shipping Pte Ltd v Straits Bunker Supplies Pte Ltd | **YES** — off-spec bunker fuel dispute; application for specific production of delivery/lab records (Summons HC/SUM 902/2026) |
| `MAT-2026-0398` | Sale of 88 Orchard Grove #12-04 | NO — residential conveyancing (sale & purchase) |
| `MAT-2026-0455` | Novagen Biotech Pte Ltd — Series B financing | NO — venture financing / shareholders agreement |
| `MAT-2026-0512` | BrightPath Learning Pte Ltd — Vietnam trademark licence | NO — trademark licensing for regional expansion |

## Ground truth — corporate/transactional set

Companion set to the litigation dataset. Same fictional firm (Wee Corporate
Law LLC) as `MAT-2026-0455` above, same flat matter-reference folder
structure, same file conventions.

Suggested test prompt: *"Draft a shareholders agreement for a two-party
joint venture, including reserved matters, a deadlock mechanism and
restrictions on the transfer of shares."* Secondary prompts worth running:

- *"Find our best drag-along and tag-along wording."* — tests whether
  `MAT-2026-0473` is surfaced despite never using either term.
- *"What is our current model deadlock clause?"* — tests supersession: the
  right answer is `MAT-2026-0561/05`, not `MAT-2024-0912/03`.
- *"Show me everything we have on Trashi Digital."* — should surface the
  automatically-flagged conflict against `MAT-2024-0912` (see Conflicts,
  below).

| Folder | Matter | Relevant to the shareholders-agreement prompt? |
|---|---|---|
| `MAT-2026-0561` | Aurora Ventures Pte Ltd — Maximus / Trashi joint venture | **PRIMARY.** `05_final_...docx` is the executed, partner-approved model precedent. This is the single correct answer. |
| `MAT-2026-0473` | Trashi Digital Pte Ltd — Series A | **SECONDARY.** `04_final_investment_and_subscription_deed.docx` is functionally a shareholders agreement under different terminology. Should be surfaced; should rank below `MAT-2026-0561/05`. |
| `MAT-2024-0912` | Vantage Foods Holdings Pte Ltd — Pratim / Maximus joint venture | **TRAP.** Topically a near-perfect keyword match, but superseded — outdated statutory citations, superseded arbitration rules, and a deadlock clause the firm has expressly stopped using. Should be found, flagged as outdated, and **not** used as the drafting base. |
| `MAT-2026-0508` | Maximus Property Holdings — 41 Kallang Way tenancy | NO — same client, wrong document type. |
| `MAT-2026-0530` | Pratim Logistics Pte Ltd — COO hire | NO — employment agreement and mutual NDA. |

### Document-level ground truth within `MAT-2026-0561`

| File | Expected behaviour |
|---|---|
| `05_final_joint_venture_shareholders_agreement.docx` | **Retrieve and use.** Execution version, 5 Aug 2026, marked partner-approved. |
| `07_shareholders_agreement_v2_FINAL_final.docx` | **Reject as a stale duplicate.** No execution date, no partner approval marking, and three clauses regressed to the pre-markup drafting (casting vote restored at clause 3, shotgun deadlock restored at clause 5, short-form reserved matters at clause 4). Deliberately named the way real files in a shared drive are named. A system that ranks on filename or apparent completeness will pick this one. |
| `03_draft_...docx` | Retrieve as provenance only. Contains the partner markup showing *why* the final clauses read as they do. |
| `04_redlined_...docx` | Retrieve as provenance only. Counterparty positions and internal responses. |
| `06_file_note_completion.docx` | Distractor — same matter, no drafting content. |

### Traps, and what each one tests

**Version discrimination.** `05` and `07` in `MAT-2026-0561` are the same
agreement. `07` is the version someone saved before the partner's comments
were worked in. The only reliable signals are the execution date, the
approval marking, and the substantive divergence at clauses 3, 4 and 5 — the
app's search ranking (`backend/app/search.py`, step 4) picks these signals up
directly and rejects `07` with a stated reason regardless of filename.

**Currency and supersession.** `MAT-2024-0912/03` cites the Contracts
(Rights of Third Parties) Act (Cap. 53B) and the Companies Act (Cap. 50) —
both pre-2020 revised-edition citations — and hard-wires the SIAC Rules (6th
Edition, 2016). `MAT-2024-0912/04_file_note_precedent_superseded.docx`
states in terms that the agreement should no longer be used and points to
`MAT-2026-0561` instead. A system with provenance and currency detection
should surface that file note alongside any hit on the 2024 agreement.

**Semantic rather than lexical matching.** `MAT-2026-0473` calls its veto
list "Consent Matters", its board the "Supervisory Board", its tag-along a
"co-sale right" and its drag-along a "compulsory sale right". The internal
memo at `05` says explicitly that the document will be invisible to anyone
searching by the usual labels — which is the point of the test.

**Access control.**
`MAT-2026-0530/05_internal_memo_privileged_covenant_risk.docx` is marked
privileged and partner-only, and contains advice on inducement risk plus a
reference to an unannounced sale process. It should be excluded from results
for any user outside the matter team, and should never be used as drafting
source material — see "Ethical walls" in the root `README.md`.

**Conflicts.** Pratim Capital Partners (`MAT-2024-0912`) is recorded as
adverse to Trashi Digital (`MAT-2026-0473`, `MAT-2026-0561`); the conflict
is narrated in `MAT-2024-0912/04` and structurally recorded in
`MAT-2024-0912/05_conflicts_desk_note.docx`, whose explicit `Client:` /
`Counterparty:` fields are what the automatic exact-match conflict check
(`backend/app/conflicts.py`) actually keys off — re-seeding the corpus
should raise a live, unacknowledged flag on `MAT-2026-0473`'s row in the
Matters view, exactly the way the litigation set's own conflict does (next
paragraph).

**Same-client noise.** Maximus Retail Group appears in four of the five
corporate matters and Pratim in two. Client-name matching alone will pull
the wrong documents.

## Ground truth — Northstar & Vale set (`MAT-2026-0601`–`0604`)

A second, plain-text fictional firm — same flat matter-reference structure
— that widens practice-area coverage and supplies a second, self-contained
example of the automatic conflict check:

| Folder | Matter | Notes |
|---|---|---|
| `MAT-2026-0601` | HelioGrid Energy — acquisition of Meridian Infrastructure Holdings' solar business | Client: HelioGrid. Counterparty: Meridian Infrastructure Holdings. Asset purchase, draft → partner redline → executed → completion note. |
| `MAT-2026-0602` | Meridian Infrastructure Holdings v Eastbank Utilities | Client: Meridian Infrastructure Holdings — the same company recorded as *counterparty* in `MAT-2026-0601`. Ingesting this matter (after `0601`) trips the automatic positional-conflict check: the firm is now acting *for* a party it was recently acting *against*. |
| `MAT-2026-0603` | LumenArc Technologies — Series B with Cedar Ventures | A second, independent venture-financing/shareholders-agreement matter — useful for testing that ranking correctly separates near-duplicate-in-kind matters (this one, `MAT-2026-0455`, `MAT-2026-0473`, `MAT-2026-0561`) by party rather than by document type alone. |
| `MAT-2026-0604` | Northstar Health Systems — CloudMosaic data breach | Technology/privacy matter; no overlap with the others. |

## File formats
Documents are provided as **.docx** (Word), **.pdf**, or plain **.txt**
(the Northstar & Vale set only), matching how each would realistically be
produced and stored in a small firm:

- **Court submissions and contracts** → `.docx`, formatted with proper court
  headings, clause numbering, and genuine redline-style markup — struck-through
  deletions, underlined insertions, and marginal reviewer comments — kept
  strictly in black and white (no coloured text or highlighting) for a
  professional, print-ready look.
- **Client correspondence** → `.pdf`, formatted as a printed email thread on
  firm letterhead, exactly as a fee earner would save it to the client folder.
- **Billing summaries** → `.pdf`, formatted as a firm invoice/statement with
  a time-entry table and GST calculation (the 2024 matter bills GST at 8%,
  the 2026 matters at 9% — a small, realistic period signal for any
  date-inference feature).

## The "draft" stage shows real internal review
The `03_draft_...` document in most matters is not a bare skeleton — it is
the associate's first-pass draft as it came back from the supervising
partner: substantive paragraphs are struck through and rewritten, with
marginal comments explaining *why* (e.g. "anchor to the exhibit reference,"
"confirm the clause number against the executed contract"). This reflects
the actual lifecycle of a document inside a firm — draft, partner markup,
clean version, then (for contracts) counterparty negotiation — and gives a
retrieval system a genuinely harder task in telling draft from final than a
document that simply says "DRAFT" at the top.

## A note on submission headings
The specific-production submissions do **not** use generic IRAC labels
("Issue / Rule / Application / Conclusion"). Each heading instead states the
substantive proposition it is arguing, e.g. *"The Defendant's Own Recall
Notice Confirms the Documents Exist and Are Within Its Control"* — matching
how point headings actually read in filed Singapore court submissions.

## Document types included per matter
Each folder contains a realistic mix designed to test whether your
retrieval system can distinguish *directly relevant* documents from
*same-client noise*:

- Client correspondence (email threads, including tangents/unrelated asks —
  a common real-world confuser)
- Billing summary (time entries, sometimes referencing unrelated sub-matters)
- Draft submission/contract (marked "DRAFT", with internal drafting notes —
  useful for testing whether your system distinguishes draft vs final)
- Final/executed submission or contract
- Redlined/marked-up versions with tracked-changes-style formatting and
  reviewer comments (for the transactional matters)
- At least one "distractor" document — a file note, internal memo, or
  standalone advisory note that is topically adjacent but should NOT be
  surfaced for a specific-production query even though it's in the same
  matter folder

## Suggested test prompts
> "Draft a legal argument in IRAC for a request for specific production under
> the Rules of Court 2021."

A well-tuned retrieval system should surface the specific-production
submissions from **both** litigation matters (`HC-S-214-2026`,
`HC-ADM-88-2026`) — even though the query never names either party — and
should **not** surface anything from the transactional matters, nor the
same-matter noise documents (the unrelated charterparty redline, the
unrelated draft supply agreement with a replacement vendor).

> "Draft a shareholders agreement for a two-party joint venture, including
> reserved matters, a deadlock mechanism and restrictions on the transfer of
> shares."

See "Ground truth — corporate/transactional set" above.

## Notes on legal content
References to "Order 11 Rule 3, Rules of Court 2021" and the specific
production threshold (materiality, existence/control, necessity,
proportionality), the clause drafting in the corporate set, and all other
legal content in this corpus are simplified and generic — written for
realism in a demo dataset, not as a verified statement of Singapore law. Do
not rely on or reuse any of it in practice without independent review.
