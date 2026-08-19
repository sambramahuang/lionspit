# Synthetic Law Firm Document Repository — Hackathon Demo Dataset

All matters, parties, firms, and individuals below are **entirely fictional**,
created for demonstrating a document-classification/retrieval solution.
Do not use any names or facts herein as real precedent or real party data.

## Purpose
This repository simulates a small Singapore law firm's flat, client-name-based
folder structure (no case management system) — mixed document types, some
relevant to a "specific production" query and some irrelevant "noise", exactly
as they'd sit in a real shared drive.

Folders are named by **court suit/summons number** (for litigation matters)
or **internal firm matter reference number** (for transactional matters) —
never by client name — matching how a small firm's shared drive is actually
organised.

## Ground truth for evaluation

| Folder | Matter | Involves an application for **specific production**? |
|---|---|---|
| `HC-S-214-2026` | Meridian Robotics Pte Ltd v Vantage Components Pte Ltd | **YES** — breach of supply contract; application for specific production of QA/defect logs (Summons HC/SUM 611/2026) |
| `HC-ADM-88-2026` | Harborview Shipping Pte Ltd v Straits Bunker Supplies Pte Ltd | **YES** — off-spec bunker fuel dispute; application for specific production of delivery/lab records (Summons HC/SUM 902/2026) |
| `MAT-2026-0398` | Sale of 88 Orchard Grove #12-04 | NO — residential conveyancing (sale & purchase) |
| `MAT-2026-0455` | Novagen Biotech Pte Ltd — Series B financing | NO — venture financing / shareholders agreement |
| `MAT-2026-0512` | BrightPath Learning Pte Ltd — Vietnam trademark licence | NO — trademark licensing for regional expansion |

## File formats
Documents are provided as **.docx** (Word) or **.pdf**, matching how each
would realistically be produced and stored in a small firm:

- **Court submissions and contracts** → `.docx`, formatted with proper court
  headings, clause numbering, and genuine redline-style markup — struck-through
  deletions, underlined insertions, and marginal reviewer comments — kept
  strictly in black and white (no coloured text or highlighting) for a
  professional, print-ready look.
- **Client correspondence** → `.pdf`, formatted as a printed email thread on
  firm letterhead, exactly as a fee earner would save it to the client folder.
- **Billing summaries** → `.pdf`, formatted as a firm invoice/statement with
  a time-entry table and GST calculation.

## The "draft" stage shows real internal review
The `03_draft_...` document in each matter is not a bare skeleton — it is the
associate's first-pass draft as it came back from the supervising partner:
substantive paragraphs are struck through and rewritten, with marginal
comments explaining *why* (e.g. "anchor to the exhibit reference," "confirm
the clause number against the executed contract"). This reflects the actual
lifecycle of a document inside a firm — draft, partner markup, clean version,
then (for contracts) counterparty negotiation — and gives a retrieval system
a genuinely harder task in telling draft from final than a document that
simply says "DRAFT" at the top.

## A note on submission headings
The specific-production submissions do **not** use generic IRAC labels
("Issue / Rule / Application / Conclusion"). Each heading instead states the
substantive proposition it is arguing, e.g. *"The Defendant's Own Recall
Notice Confirms the Documents Exist and Are Within Its Control"* — matching
how point headings actually read in filed Singapore court submissions.

## Document types included per matter
Each folder contains a realistic mix designed to test whether your retrieval
system can distinguish *directly relevant* documents from *same-client noise*:

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

## Suggested test prompt
> "Draft a legal argument in IRAC for a request for specific production under
> the Rules of Court 2021."

A well-tuned retrieval system should surface `03_draft_submission_specific_production.txt`
and `04_final_submission_specific_production.txt` from Cases 01 and 02, and
should **not** surface any documents from Cases 03–05, nor the distractor/noise
files within Cases 01–02 (e.g. the unrelated draft supply agreement in Case 01,
the charterparty redline in Case 02).

## Notes on legal content
References to "Order 11 Rule 3, Rules of Court 2021" and the specific
production threshold (materiality, existence/control, necessity,
proportionality) are simplified and generic — written for realism in a demo
dataset, not as a verified statement of law. Verify against the actual ROC
2021 and current practice directions before relying on this for any real
submission.
