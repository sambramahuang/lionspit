"""
FastAPI entrypoint. Run with:  uvicorn app.main:app --reload --port 8000
(from inside backend/, with your virtualenv active and .env filled in).
"""
from fastapi import Depends, FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import conflicts as conflicts_module, ingestion, matters, search as search_module, vectorstore
from app.auth import CurrentUser, get_current_user, require_partner
from app.config import settings
from app.drafting import generate_draft
from app.models import (
    ClauseSearchRequest,
    ClauseSearchResponse,
    ConflictFlag,
    DocumentRecord,
    DraftRequest,
    DraftResponse,
    DocumentApprovalRequest,
    ExtractedTextResponse,
    IngestResult,
    LineageResponse,
    MatterSummary,
    MatterWallInfo,
    MatterWallRequest,
    MeResponse,
    SearchRequest,
    SearchResponse,
)

app = FastAPI(title="Precedent Bank API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "documents_indexed": len(vectorstore.list_all())}


@app.get("/api/me", response_model=MeResponse)
def me(user: CurrentUser = Depends(get_current_user)):
    return MeResponse(email=user.email, is_partner=user.is_partner)


@app.post("/api/ingest", response_model=list[IngestResult])
async def ingest_documents(files: list[UploadFile] = File(...), _user: CurrentUser = Depends(get_current_user)):
    """
    Accepts one or more files, extracts text, auto-tags metadata via
    the LLM, and indexes each one. No manual tagging or reorganizing --
    this endpoint IS the "low-effort capture" pillar.
    """
    results = []
    for f in files:
        try:
            content = await f.read()
            text = ingestion.extract_text(f.filename, content)
            if not text.strip():
                raise ValueError("No extractable text found in file.")
            metadata = ingestion.extract_metadata_with_llm(f.filename, text)
            doc_id = ingestion.new_doc_id()

            meta_dict = metadata.model_dump()
            meta_dict["filename"] = f.filename
            meta_dict["usage_count"] = 0

            vectorstore.add_document(doc_id, text, meta_dict)
            vectorstore.add_document_clauses(doc_id, ingestion.split_into_clauses(text))

            new_matter_key = matters.cluster_key(meta_dict)
            found_conflicts = conflicts_module.detect_conflicts(meta_dict, new_matter_key)
            for c in found_conflicts:
                vectorstore.flag_conflict(new_matter_key, c["reason"], doc_id)

            results.append(IngestResult(
                doc_id=doc_id, filename=f.filename, metadata=metadata, status="ingested",
                conflict_warnings=[c["reason"] for c in found_conflicts],
            ))
        except Exception as e:  # noqa: BLE001 -- surface per-file errors, don't kill the batch
            results.append(IngestResult(
                doc_id="", filename=f.filename, metadata=ingestion.DocumentMetadata(), status="error", error=str(e)
            ))
    return results


@app.post("/api/extract-text", response_model=ExtractedTextResponse)
async def extract_text(file: UploadFile = File(...), _user: CurrentUser = Depends(get_current_user)):
    """
    Text extraction only -- reuses the exact same extraction ingestion.py
    uses for real uploads, but deliberately does NOT call the metadata LLM
    and does NOT touch vectorstore at all. For attaching a document's text
    as one-off search context (e.g. a lawyer's own case file) without it
    becoming a permanent, browsable precedent in the library.
    """
    content = await file.read()
    text = ingestion.extract_text(file.filename, content)
    if not text.strip():
        raise HTTPException(status_code=400, detail="No extractable text found in file.")
    return ExtractedTextResponse(filename=file.filename, text=text)


@app.get("/api/documents", response_model=list[DocumentRecord])
def list_documents(user: CurrentUser = Depends(get_current_user)):
    """
    Walled documents are still listed, not omitted -- a lawyer should see
    that a document exists and is walled off, not have it silently absent
    with no explanation (same "explain, don't silently drop" principle
    search.py's access_restricted already follows). Only the content is
    withheld: text_preview is blanked for a restricted record, and the
    frontend disables preview/approve/delete for it. The actual document
    text stays unreachable regardless -- get_document still enforces the
    wall itself for anyone who tries the doc_id directly.
    """
    records = vectorstore.list_all()
    walls = matters.load_walls()
    out = []
    for r in records:
        meta = r["metadata"]
        blocked = matters.is_blocked(meta, user.email, walls)
        out.append(DocumentRecord(
            doc_id=r["doc_id"],
            filename=meta.get("filename", r["doc_id"]),
            metadata=meta,
            usage_count=int(meta.get("usage_count", 0) or 0),
            text_preview="" if blocked else (
                (r["text"][:280] + "...") if len(r["text"]) > 280 else r["text"]
            ),
            access_restricted=blocked,
            restricted_reason=(
                "This matter is walled off. You don't have access to view it."
                if blocked else None
            ),
        ))
    return out


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str, user: CurrentUser = Depends(get_current_user)):
    record = vectorstore.get_by_id(doc_id)
    if record is None:
        raise HTTPException(404, "document not found")
    if matters.is_blocked(record["metadata"], user.email, matters.load_walls()):
        raise HTTPException(403, "This matter is walled off. You don't have access to view it.")

    meta = record["metadata"]
    return {
        "doc_id": record["doc_id"],
        "filename": meta.get("filename", record["doc_id"]),
        "metadata": meta,
        "text": record["text"],
    }


@app.delete("/api/documents")
def reset_documents(_user: CurrentUser = Depends(get_current_user)):
    vectorstore.reset()
    return {"status": "reset"}


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str, user: CurrentUser = Depends(require_partner)):
    """Removing a single wrongly-ingested or genuinely obsolete document
    used to mean wiping the entire index -- this is the actual fix.
    Partner-gated like wall edits, since it mutates a corpus every lawyer
    relies on, not just the deleter's own data. Wall-checked the same way
    every other document-returning route is: a partner personally walled
    off a matter still can't act on documents inside it."""
    record = vectorstore.get_by_id(doc_id)
    if record is None:
        raise HTTPException(404, "document not found")
    if matters.is_blocked(record["metadata"], user.email, matters.load_walls()):
        raise HTTPException(403, "This matter is walled off. You don't have access to view it.")
    vectorstore.delete_document(doc_id)
    return {"status": "deleted", "doc_id": doc_id}


@app.post("/api/documents/{doc_id}/approval", response_model=DocumentRecord)
def set_document_approval(
    doc_id: str,
    req: DocumentApprovalRequest,
    user: CurrentUser = Depends(require_partner),
):
    record = vectorstore.get_by_id(doc_id)
    if record is None:
        raise HTTPException(404, "document not found")
    if matters.is_blocked(record["metadata"], user.email, matters.load_walls()):
        raise HTTPException(403, "This matter is walled off. You don't have access to approve it.")

    updated = vectorstore.set_document_approval(doc_id, req.approved, user.email, req.note)
    return DocumentRecord(
        doc_id=updated["doc_id"],
        filename=updated["metadata"].get("filename", doc_id),
        metadata=updated["metadata"],
        usage_count=int(updated["metadata"].get("usage_count", 0) or 0),
        text_preview=(updated["text"][:280] + "...") if len(updated["text"]) > 280 else updated["text"],
    )


@app.get("/api/lineage", response_model=LineageResponse)
def lineage(user: CurrentUser = Depends(get_current_user)):
    """Corpus-wide version-history graph: one cluster per matter, current
    document at the hub, every other version pointing to it with a reason."""
    return search_module.compute_lineage(user.email)


@app.get("/api/matters", response_model=list[MatterSummary])
def list_matters(user: CurrentUser = Depends(get_current_user)):
    return matters.summarize(user.email, user.is_partner)


@app.delete("/api/matters/{matter_key}")
def delete_matter(matter_key: str, user: CurrentUser = Depends(require_partner)):
    """A matter has no row of its own (see matters.cluster_key) -- deleting
    one means cascading through every document whose computed cluster key
    matches. Partner-gated and wall-checked the same way as delete_document."""
    if matters.is_key_blocked(matter_key, user.email, matters.load_walls()):
        raise HTTPException(403, "This matter is walled off. You don't have access to delete it.")
    doc_ids = [r["doc_id"] for r in vectorstore.list_all() if matters.cluster_key(r["metadata"]) == matter_key]
    if not doc_ids:
        raise HTTPException(404, "matter not found")
    for doc_id in doc_ids:
        vectorstore.delete_document(doc_id)
    return {"status": "deleted", "matter_key": matter_key, "deleted_count": len(doc_ids)}


@app.post("/api/matters/{matter_key}/wall", response_model=MatterWallInfo)
def set_matter_wall(matter_key: str, req: MatterWallRequest, user: CurrentUser = Depends(require_partner)):
    allowed = sorted({e.strip().lower() for e in req.allowed_emails if e.strip()})
    return vectorstore.set_wall(matter_key, req.walled, allowed, user.email)


@app.post("/api/matters/{matter_key}/conflict/acknowledge", response_model=ConflictFlag)
def acknowledge_conflict(matter_key: str, user: CurrentUser = Depends(require_partner)):
    """Marks a conflict flag reviewed -- doesn't delete the record, just
    stops it surfacing as unresolved. A fresh detection later (see
    vectorstore.flag_conflict) resets it, so acknowledging today doesn't
    silence a genuinely new signal tomorrow."""
    result = vectorstore.acknowledge_conflict(matter_key, user.email)
    if result is None:
        raise HTTPException(404, "no conflict flag for this matter")
    return result


@app.post("/api/search", response_model=SearchResponse)
def search(req: SearchRequest, user: CurrentUser = Depends(get_current_user)):
    if not req.query.strip():
        raise HTTPException(400, "query must not be empty")
    return search_module.run_search(req, user.email)


@app.post("/api/search/clauses", response_model=ClauseSearchResponse)
def search_clauses(req: ClauseSearchRequest, user: CurrentUser = Depends(get_current_user)):
    if not req.query.strip():
        raise HTTPException(400, "query must not be empty")
    return search_module.run_clause_search(req, user.email)


@app.post("/api/draft", response_model=DraftResponse)
def draft(req: DraftRequest, user: CurrentUser = Depends(get_current_user)):
    if not req.doc_ids:
        raise HTTPException(400, "doc_ids must not be empty")
    return generate_draft(req, user.email)
