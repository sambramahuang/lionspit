"""
Turns a raw uploaded file into (text, DocumentMetadata) with no manual
tagging required -- this is the "low-effort capture" pillar. We extract
text per file type, then hand it to the LLM with a strict JSON schema
prompt to auto-populate the metadata fields called for in the brief.
"""

import io
import re
import uuid

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from pypdf import PdfReader

from app.llm_client import call_llm_json, transcribe_image
from app.models import DocumentMetadata

METADATA_SYSTEM_PROMPT = """You are a legal document triage assistant at a law firm.
You read a document (which may be messy, informal, or an internal file) and
extract structured metadata about it. You are careful and literal: only fill
in a field if the document (or its filename) actually gives evidence for it.
If a field cannot be determined, use null (for strings) or false (for
booleans) rather than guessing.

Respond with ONLY a single JSON object, no prose, no markdown fences, with
exactly these keys:

{
  "client_name": string or null -- the specific named client/company/primary party this document is for (e.g. "Alpha Robotics Pte Ltd"). Identifies WHICH matter this is, as distinct from matter_type (WHAT KIND of matter). Two unrelated companies' documents must never share a client_name even if matter_type/practice_area/jurisdiction match. NEVER the law firm itself (its own name on the letterhead, or the fee earner's firm in a signature block) -- the firm is not a party to the matter it is handling, it is the one handling it. Client correspondence is written FROM the firm TO the client: the firm's own name appearing as the sender is not evidence that the firm is client_name or counterparty_name for anything,
  "counterparty_name": string or null -- the other specific named party to the MATTER itself, if any (e.g. the landlord if client_name is the tenant, the other side of a deal or dispute) -- not the other party to this particular piece of correspondence. A letter from the firm to its client names the firm and the client, neither of which is the matter's counterparty; leave counterparty_name null if the document doesn't otherwise name the matter's actual other side. If a document does name the matter's two real parties, extract BOTH client_name and counterparty_name even if it's unclear from context alone which one is "the client" -- consistently naming both parties matters more than which field each goes in,
  "matter_reference": string or null -- the firm's internal matter/file number or a court case/suit/summons-file number, ONLY if the document itself states one for the overarching matter (e.g. "HC/S 214/2026", "MAT-2026-0398"). Extract just the bare code, not the surrounding phrase it appears in (drop prefixes like "Matter", "Suit No.", "Ref:"). If the document is itself a specific application/summons WITHIN a larger suit (e.g. "Summons No. HC/SUM 611/2026"), extract the overarching suit/matter number it belongs to, not the summons number -- the summons is one step in the matter, not the matter itself. Two different documents that are genuinely part of the same client engagement should get the identical reference if the text supports it; leave null rather than guessing one that isn't actually stated,
  "matter_type": string or null,
  "practice_area": string or null,
  "jurisdiction": string or null,
  "industry": string or null,
  "client_type": string or null,
  "transaction_value": string or null,
  "document_date": string or null (YYYY-MM-DD if determinable, else the raw date text),
  "responsible_lawyer": string or null,
  "counterparty_type": string or null,
  "document_type": one of "Contracts / Agreements", "Legal opinions / Advice", "Pleadings / Court filings", "Client correspondence", "Internal memo", "Billing", "Other", or null -- what KIND of document this is, not what stage of drafting it's at (that's is_draft_or_model below) -- this is the firm's own work product, never a primary-law category like legislation or a reported judgment,
  "matter_completed": boolean or null,
  "document_executed": boolean or null,
  "is_draft_or_model": one of "draft", "model", "executed", "unknown",
  "version": string or null,
  "partner_approved": boolean or null,
  "short_description": a one-sentence plain-English description of what this document is and what makes it useful as a precedent,
  "confidentiality": one of "public", "internal", "restricted"
}
"""


# A genuine scanned page with no text layer returns "" from pypdf, not a
# handful of stray characters -- this threshold just also catches a text
# layer that's present but junk (e.g. a lone watermark), where OCR is still
# worth trying rather than treating a few leftover characters as "has text".
_MIN_EXTRACTED_TEXT_CHARS = 20
_MAX_OCR_PAGES = 8  # bounds cost/latency on a pathologically large scan


def _ocr_pdf(content: bytes) -> str:
    """OCR fallback for a PDF whose text layer is empty or near-empty -- a
    scanned document, not something pypdf can fix by trying harder. Renders
    each page to an image via PyMuPDF (no external binary needed, unlike
    poppler/tesseract -- see llm_client.transcribe_image's docstring for
    why that matters on Vercel) and transcribes it with the vision model.
    Capped at _MAX_OCR_PAGES so one large scanned document doesn't turn a
    single upload into dozens of vision calls."""
    doc = fitz.open(stream=content, filetype="pdf")
    pages_text = []
    for page in doc[:_MAX_OCR_PAGES]:
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))  # ~144 DPI
        try:
            pages_text.append(transcribe_image(pixmap.tobytes("png")))
        except Exception:
            continue  # one page's OCR failing shouldn't sink the whole document
    return "\n\n".join(t for t in pages_text if t.strip())


def extract_text(filename: str, content: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if len(text.strip()) < _MIN_EXTRACTED_TEXT_CHARS:
            # Most likely a scanned document rather than a native PDF --
            # try OCR before giving up. Falls back to whatever pypdf found
            # (usually empty) if OCR itself fails for any reason, so a
            # vision-API outage degrades to today's behavior (ingestion
            # fails with "no extractable text") instead of blocking on it.
            try:
                ocr_text = _ocr_pdf(content)
                if ocr_text.strip():
                    return ocr_text
            except Exception:
                pass
        return text
    if lower.endswith(".docx"):
        doc = DocxDocument(io.BytesIO(content))
        # Real redlines in the wild are usually manual strikethrough/underline
        # character formatting, not actual Word tracked-changes XML -- so a
        # naive paragraph.text read concatenates the "deleted" and "inserted"
        # runs back-to-back with no separator (e.g. "12 weeks10 weeks"),
        # garbling both the metadata LLM's input and clause-search embeddings.
        # Skipping struck-through runs recovers the clean, current reading.
        lines = []
        for p in doc.paragraphs:
            lines.append("".join(r.text for r in p.runs if not r.font.strike))
        return "\n".join(lines)
    # .txt and anything else: best-effort decode
    return content.decode("utf-8", errors="ignore")


def extract_metadata_with_llm(filename: str, text: str) -> DocumentMetadata:
    # Cap the text we send -- metadata extraction doesn't need the whole
    # document, and this keeps ingestion fast and cheap across 20-50 files.
    excerpt = text[:6000]
    user_prompt = f"Filename: {filename}\n\nDocument text:\n{excerpt}"
    data = call_llm_json(METADATA_SYSTEM_PROMPT, user_prompt, max_tokens=600)
    return DocumentMetadata(**data)


def new_doc_id() -> str:
    return f"doc_{uuid.uuid4().hex[:10]}"


# Matches a line starting a numbered legal clause -- "1. ", "2.3 ", "4.1.2)",
# "Section 3:", "Clause 5.2", "Article 10" -- the conventions real legal
# drafting actually uses for top-level clause numbering. Deliberately does
# NOT match lettered sub-points like "(a)" -- those belong inside their
# parent clause rather than becoming their own fragment, or clause search
# would return dozens of tiny, context-free slivers per document.
_CLAUSE_HEADER_RE = re.compile(
    r"^[ \t]{0,3}(?:(?:clause|section|article)\s+\d+(?:\.\d+)*[:.]?|\d+(?:\.\d+){0,3}[.)])\s+",
    re.MULTILINE | re.IGNORECASE,
)

_MIN_CLAUSE_MARKERS = 3  # below this, the doc isn't reliably clause-numbered
_MAX_CLAUSES_PER_DOC = 60  # bound embedding calls on pathological input
_TARGET_WORDS = 220  # fallback paragraph-merge target size
_MAX_FALLBACK_WORDS = 500  # split any single paragraph longer than this


def _label_for(chunk: str) -> str:
    first_line = (chunk.strip().splitlines()[0] if chunk.strip() else chunk).strip()
    if len(first_line) <= 100:
        return first_line
    return first_line[:100].rsplit(" ", 1)[0] + "…"


def _merge_and_cap_paragraphs(paragraphs: list[str]) -> list[str]:
    """Fallback chunking for documents with no reliable clause numbering:
    merge consecutive short paragraphs up to a target size (so single
    sentences don't become their own clause), and split any paragraph
    that's still too long into fixed-size word windows (so one giant
    unbroken block of text doesn't become a single unsearchable "clause")."""
    chunks: list[str] = []
    buffer: list[str] = []
    buffer_words = 0

    def flush():
        if buffer:
            chunks.append("\n\n".join(buffer))

    for p in paragraphs:
        words = p.split()
        if len(words) > _MAX_FALLBACK_WORDS:
            flush()
            buffer, buffer_words = [], 0
            for i in range(0, len(words), _MAX_FALLBACK_WORDS):
                chunks.append(" ".join(words[i : i + _MAX_FALLBACK_WORDS]))
            continue

        buffer.append(p)
        buffer_words += len(words)
        if buffer_words >= _TARGET_WORDS:
            flush()
            buffer, buffer_words = [], 0

    flush()
    return chunks


def split_into_clauses(text: str) -> list[dict]:
    """Splits a document's text into individually searchable "clauses" --
    this is what powers clause-level search (finding the one indemnity
    provision buried in a 40-page agreement, not just the agreement
    itself). No LLM call here: numbered-clause detection is a cheap,
    deterministic regex pass that matches how legal documents are
    actually structured, so ingestion cost/latency doesn't scale with
    corpus size the way an LLM-per-clause approach would. Falls back to
    paragraph-based chunking for documents with no reliable numbering
    (emails, memos, informal notes) rather than forcing a legal-clause
    shape onto text that doesn't have one.

    Returns a list of {"label": str, "text": str} in document order.
    """
    matches = list(_CLAUSE_HEADER_RE.finditer(text))
    if len(matches) >= _MIN_CLAUSE_MARKERS:
        raw_chunks = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            chunk = text[start:end].strip()
            if chunk:
                raw_chunks.append(chunk)
    else:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        raw_chunks = (
            _merge_and_cap_paragraphs(paragraphs)
            if paragraphs
            else ([text.strip()] if text.strip() else [])
        )

    if len(raw_chunks) > _MAX_CLAUSES_PER_DOC:
        # Merge down to the cap by combining adjacent chunks evenly rather
        # than truncating -- every part of the document stays searchable,
        # just at coarser granularity.
        factor = -(-len(raw_chunks) // _MAX_CLAUSES_PER_DOC)  # ceil div
        raw_chunks = [
            "\n\n".join(raw_chunks[i : i + factor])
            for i in range(0, len(raw_chunks), factor)
        ]

    return [{"label": _label_for(c), "text": c} for c in raw_chunks]
