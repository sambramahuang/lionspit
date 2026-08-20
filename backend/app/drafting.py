"""
Generates a draft strictly grounded in the selected precedent documents,
with an inline citation marker after every substantive clause pointing
back to its source. This is the "show the source of every important
clause" step of the demo, and the main way the tool earns trust.

Source documents are past matters, not the new one being drafted -- so
their clause structure and drafting language are reusable, but the old
matter's own party names, figures, and dates are not facts about the new
one. The system prompt has the model swap those for bracketed
placeholders unless the caller's query/instructions actually supply the
new matter's facts, rather than silently carrying an old client's name or
a stale dollar figure into a new draft.
"""
import re

from app import matters, vectorstore
from app.llm_client import call_llm_text
from app.models import Citation, DraftRequest, DraftResponse

DRAFT_SYSTEM_PROMPT = """You are a senior drafting assistant at a law firm. You draft
using ONLY the source documents you are given -- you never invent clauses,
figures, or terms that aren't grounded in a source.

Rules:
1. After every clause, sentence, or defined term you draw from a source,
   insert a citation marker immediately after it: [[n]] where n is the
   source's number as given below (source 1, source 2, ...). This is
   mandatory for every such clause with NO exceptions -- including a
   clause whose facts you've replaced with a placeholder under rule 3
   below. Swapping out a name or figure does not change where the
   clause's structure and language came from, so it still needs its
   citation marker. Never let rule 3 cause you to skip a citation.
2. If the request calls for something the sources do not cover, do NOT
   invent it. Instead write: [[GAP: short description of what's missing]]
   at that point in the draft, in place of fabricated text.
3. The sources belong to a DIFFERENT, earlier matter, so their party
   names, company names, individual names, monetary figures,
   percentages, share counts, and specific dates are not facts about the
   new matter. Replace any such fact with a single-bracket placeholder
   -- e.g. [Party A], [Company Name], [$ Amount], [Effective Date] --
   unless the drafting request or additional instructions state the
   actual fact for the new matter, in which case use that instead.
   Generic defined terms (e.g. "the Company", "Shareholders") are not
   matter-specific facts and stay as-is. This rule only changes which
   words appear in the clause -- it never removes the citation marker
   rule 1 requires for that same clause.
4. Where sources conflict (e.g. different indemnity caps), prefer the
   source explicitly marked "partner approved" if one exists, and note the
   conflict briefly in a trailing "Drafting notes" section.
5. Write in standard legal drafting style, with numbered clauses where
   appropriate. Do not include any preamble outside the draft itself other
   than the "Drafting notes" section at the end if needed.
"""


_MARKER_RE = re.compile(r"\[\[(?:\d+|GAP:[^\]]*)\]\]")


def _looks_like_heading_or_structural(paragraph: str) -> bool:
    """True for a document title, party-block caption, or section heading
    -- text the citation rule was never meant to reach, as opposed to an
    actual drafted clause. Real clauses in legal drafting are written
    sentences (end in ./;/?) of some minimum length; headings/captions/
    ALL-CAPS titles are short and don't read as sentences."""
    s = paragraph.strip()
    if not s or len(s) < 20:
        return True
    if not re.search(r"[.;?]\s*$", s):
        return True
    letters = re.sub(r"[^A-Za-z]", "", s)
    if letters and len(re.sub(r"[^A-Z]", "", s)) / len(letters) > 0.85:
        return True  # ALL-CAPS title line, e.g. "SHAREHOLDERS AGREEMENT"
    return False


def _flag_uncited_clauses(draft_text: str) -> tuple[str, list[str]]:
    """Safety net for DRAFT_SYSTEM_PROMPT rule 1 ("every clause needs a
    [[n]] or [[GAP:...]] marker, no exceptions"): the model doesn't always
    comply. Scans each paragraph for a citation/gap marker; a substantive
    paragraph with neither is effectively an ungrounded, AI-generated
    clause the prompt's own rules should have caught -- flagged with an
    inline [[UNCITED]] marker (rendered as a warning badge, same family as
    [[GAP:...]]) so a compliance slip surfaces as a visible warning in the
    drafted document instead of silently reading like any other sourced
    clause. Returns the flagged text plus a short excerpt of each flagged
    paragraph for the summary panel."""
    paragraphs = draft_text.split("\n\n")
    flagged_excerpts = []
    out = []
    for p in paragraphs:
        stripped = p.strip()
        if stripped and not _MARKER_RE.search(p) and not _looks_like_heading_or_structural(p):
            out.append("[[UNCITED]] " + p)
            flagged_excerpts.append(stripped[:160] + ("..." if len(stripped) > 160 else ""))
        else:
            out.append(p)
    return "\n\n".join(out), flagged_excerpts


def _build_source_block(idx: int, doc_id: str, meta: dict, text: str) -> str:
    header = (
        f"Source {idx} (doc_id={doc_id}, filename={meta.get('filename')}, "
        f"type={meta.get('document_type')}, date={meta.get('document_date')}, "
        f"partner_approved={meta.get('partner_approved')}, version={meta.get('version')}):"
    )
    # Cap each source's contribution so a handful of docs stays well within budget.
    return header + "\n" + text[:4000]


def generate_draft(req: DraftRequest, user_email: str) -> DraftResponse:
    # get_by_id bypasses /api/documents/{doc_id}'s wall check, so it's
    # re-applied here -- otherwise a walled document's full text could leak
    # into a draft via a doc_id the caller isn't otherwise allowed to see.
    walls = matters.load_walls()
    records = []
    for doc_id in req.doc_ids:
        rec = vectorstore.get_by_id(doc_id)
        if rec and not matters.is_blocked(rec["metadata"], user_email, walls):
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

    # Runs against the pristine draft_text above (citations/gaps already
    # extracted) so the [[UNCITED]] markers it inserts can't shift offsets
    # or get mistaken for a real citation/gap.
    flagged_draft_text, flagged_uncited = _flag_uncited_clauses(draft_text)

    return DraftResponse(
        draft_text=flagged_draft_text,
        citations=citations,
        gaps=gaps,
        flagged_uncited=flagged_uncited,
    )
