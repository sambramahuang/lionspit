"""
Turns a raw uploaded file into (text, DocumentMetadata) with no manual
tagging required -- this is the "low-effort capture" pillar. We extract
text per file type, then hand it to the LLM with a strict JSON schema
prompt to auto-populate the metadata fields called for in the brief.
"""
import io
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
