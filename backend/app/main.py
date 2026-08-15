"""
FastAPI entrypoint. Run with:  uvicorn app.main:app --reload --port 8000
(from inside backend/, with your virtualenv active and .env filled in).
"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import ingestion, search as search_module, vectorstore
from app.config import settings
from app.drafting import generate_draft
from app.models import (
    DocumentRecord,
    DraftRequest,
    DraftResponse,
    IngestResult,
    LineageResponse,
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


@app.post("/api/ingest", response_model=list[IngestResult])
async def ingest_documents(files: list[UploadFile] = File(...)):
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
            results.append(IngestResult(doc_id=doc_id, filename=f.filename, metadata=metadata, status="ingested"))
        except Exception as e:  # noqa: BLE001 -- surface per-file errors, don't kill the batch
            results.append(IngestResult(
                doc_id="", filename=f.filename, metadata=ingestion.DocumentMetadata(), status="error", error=str(e)
            ))
    return results


@app.get("/api/documents", response_model=list[DocumentRecord])
def list_documents():
    records = vectorstore.list_all()
    out = []
    for r in records:
        meta = r["metadata"]
        out.append(DocumentRecord(
            doc_id=r["doc_id"],
            filename=meta.get("filename", r["doc_id"]),
            metadata=meta,
            usage_count=int(meta.get("usage_count", 0) or 0),
            text_preview=(r["text"][:280] + "...") if len(r["text"]) > 280 else r["text"],
        ))
    return out


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str):
    record = vectorstore.get_by_id(doc_id)
    if record is None:
        raise HTTPException(404, "document not found")

    meta = record["metadata"]
    return {
        "doc_id": record["doc_id"],
        "filename": meta.get("filename", record["doc_id"]),
        "metadata": meta,
        "text": record["text"],
    }


@app.delete("/api/documents")
def reset_documents():
    vectorstore.reset()
    return {"status": "reset"}


@app.get("/api/lineage", response_model=LineageResponse)
def lineage():
    """Corpus-wide version-history graph: one cluster per matter, current
    document at the hub, every other version pointing to it with a reason."""
    return search_module.compute_lineage()


@app.post("/api/search", response_model=SearchResponse)
def search(req: SearchRequest):
    if not req.query.strip():
        raise HTTPException(400, "query must not be empty")
    return search_module.run_search(req)


@app.post("/api/draft", response_model=DraftResponse)
def draft(req: DraftRequest):
    if not req.doc_ids:
        raise HTTPException(400, "doc_ids must not be empty")
    return generate_draft(req)
