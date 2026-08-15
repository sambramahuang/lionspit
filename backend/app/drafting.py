"""
Generates a draft strictly grounded in the selected precedent documents,
with an inline citation marker after every substantive clause pointing
back to its source. This is the "show the source of every important
clause" step of the demo, and the main way the tool earns trust.
"""
import re

from app import vectorstore
from app.llm_client import call_llm_text
from app.models import Citation, DraftRequest, DraftResponse

DRAFT_SYSTEM_PROMPT = """You are a senior drafting assistant at a law firm. You draft
using ONLY the source documents you are given -- you never invent clauses,
figures, or terms that aren't grounded in a source.

Rules:
1. After every clause, sentence, or defined term you draw from a source,
   insert a citation marker immediately after it: [[n]] where n is the
   source's number as given below (source 1, source 2, ...).
2. If the request calls for something the sources do not cover, do NOT
   invent it. Instead write: [[GAP: short description of what's missing]]
   at that point in the draft, in place of fabricated text.
3. Where sources conflict (e.g. different indemnity caps), prefer the
   source explicitly marked "partner approved" if one exists, and note the
   conflict briefly in a trailing "Drafting notes" section.
4. Write in standard legal drafting style, with numbered clauses where
   appropriate. Do not include any preamble outside the draft itself other
   than the "Drafting notes" section at the end if needed.
"""


def _build_source_block(idx: int, doc_id: str, meta: dict, text: str) -> str:
    header = (
        f"Source {idx} (doc_id={doc_id}, filename={meta.get('filename')}, "
        f"type={meta.get('document_type')}, date={meta.get('document_date')}, "
        f"partner_approved={meta.get('partner_approved')}, version={meta.get('version')}):"
    )
    # Cap each source's contribution so a handful of docs stays well within budget.
    return header + "\n" + text[:4000]


def generate_draft(req: DraftRequest) -> DraftResponse:
    records = []
    for doc_id in req.doc_ids:
        rec = vectorstore.get_by_id(doc_id)
        if rec:
            records.append(rec)

    if not records:
        return DraftResponse(draft_text="No valid source documents were selected.", citations=[], gaps=[])

    source_blocks = [
        _build_source_block(i + 1, r["doc_id"], r["metadata"], r["text"])
        for i, r in enumerate(records)
    ]
    index_to_doc = {i + 1: records[i] for i in range(len(records))}

    user_prompt = (
        f"Drafting request: {req.query}\n"
        + (f"Additional instructions: {req.instructions}\n" if req.instructions else "")
        + "\n\n".join(source_blocks)
    )

    draft_text = call_llm_text(DRAFT_SYSTEM_PROMPT, user_prompt, max_tokens=2000, temperature=0.2)

    # Pull out [[n]] citation markers and turn each into a Citation with a
    # short excerpt of surrounding context for the frontend to show inline.
    citations = []
    seen_markers = set()
    for match in re.finditer(r"\[\[(\d+)\]\]", draft_text):
        marker = match.group(1)
        if marker in seen_markers:
            continue
        seen_markers.add(marker)
        src_idx = int(marker)
        rec = index_to_doc.get(src_idx)
        if not rec:
            continue
        start = max(0, match.start() - 120)
        excerpt = draft_text[start:match.start()].strip()
        citations.append(Citation(
            marker=marker,
            doc_id=rec["doc_id"],
            filename=rec["metadata"].get("filename", rec["doc_id"]),
            excerpt=excerpt[-160:],
        ))
        vectorstore.increment_usage(rec["doc_id"])

    gaps = [m.group(1).strip() for m in re.finditer(r"\[\[GAP:(.*?)\]\]", draft_text)]

    return DraftResponse(draft_text=draft_text, citations=citations, gaps=gaps)
