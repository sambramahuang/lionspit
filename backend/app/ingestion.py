"""
Turns a raw uploaded file into (text, DocumentMetadata) with no manual
tagging required -- this is the "low-effort capture" pillar. We extract
text per file type, then hand it to the LLM with a strict JSON schema
prompt to auto-populate the metadata fields called for in the brief.
"""
import io
import re
import uuid

from pypdf import PdfReader
from docx import Document as DocxDocument

from app.llm_client import call_llm_json
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
  "client_name": string or null -- the specific named client/company/primary party this document is for (e.g. "Alpha Robotics Pte Ltd"). Identifies WHICH matter this is, as distinct from matter_type (WHAT KIND of matter). Two unrelated companies' documents must never share a client_name even if matter_type/practice_area/jurisdiction match,
  "counterparty_name": string or null -- the other specific named party to this document, if any (e.g. the landlord if client_name is the tenant, or vice versa). If a document names two parties, extract BOTH client_name and counterparty_name even if it's unclear from context alone which one is "the client" -- consistently naming both parties matters more than which field each goes in,
  "matter_type": string or null,
  "practice_area": string or null,
  "jurisdiction": string or null,
  "industry": string or null,
  "client_type": string or null,
  "transaction_value": string or null,
  "document_date": string or null (YYYY-MM-DD if determinable, else the raw date text),
  "responsible_lawyer": string or null,
  "counterparty_type": string or null,
  "document_type": string or null,
  "matter_completed": boolean or null,
  "document_executed": boolean or null,
  "is_draft_or_model": one of "draft", "model", "executed", "unknown",
  "version": string or null,
  "partner_approved": boolean or null,
  "short_description": a one-sentence plain-English description of what this document is and what makes it useful as a precedent,
  "confidentiality": one of "public", "internal", "restricted"
}
"""


def extract_text(filename: str, content: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if lower.endswith(".docx"):
        doc = DocxDocument(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
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

_MIN_CLAUSE_MARKERS = 3      # below this, the doc isn't reliably clause-numbered
_MAX_CLAUSES_PER_DOC = 60    # bound embedding calls on pathological input
_TARGET_WORDS = 220          # fallback paragraph-merge target size
_MAX_FALLBACK_WORDS = 500    # split any single paragraph longer than this


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
                chunks.append(" ".join(words[i:i + _MAX_FALLBACK_WORDS]))
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
        raw_chunks = _merge_and_cap_paragraphs(paragraphs) if paragraphs else ([text.strip()] if text.strip() else [])

    if len(raw_chunks) > _MAX_CLAUSES_PER_DOC:
        # Merge down to the cap by combining adjacent chunks evenly rather
        # than truncating -- every part of the document stays searchable,
        # just at coarser granularity.
        factor = -(-len(raw_chunks) // _MAX_CLAUSES_PER_DOC)  # ceil div
        raw_chunks = [
            "\n\n".join(raw_chunks[i:i + factor])
            for i in range(0, len(raw_chunks), factor)
        ]

    return [{"label": _label_for(c), "text": c} for c in raw_chunks]
