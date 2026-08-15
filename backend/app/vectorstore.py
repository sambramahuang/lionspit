"""
Local vector store via ChromaDB. Uses Chroma's bundled local embedding
model (all-MiniLM-L6-v2, runs on-device via onnxruntime) so semantic
search works with zero extra API keys -- only document generation and
metadata extraction touch the OpenAI API. Chroma downloads that small
model from Hugging Face the first time you run it, so have internet on
hand for that one-time setup.
"""
from functools import lru_cache

import chromadb

from app.config import settings

COLLECTION_NAME = "precedents"


@lru_cache(maxsize=1)
def get_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(
        path=settings.CHROMA_PERSIST_DIR,
        settings=chromadb.config.Settings(anonymized_telemetry=False),
    )


def get_collection():
    client = get_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _flatten_metadata(meta: dict) -> dict:
    """Chroma metadata values must be str/int/float/bool -- flatten Nones
    and anything else to strings so ingestion never breaks on an edge case."""
    flat = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            flat[k] = v
        else:
            flat[k] = str(v)
    return flat


def add_document(doc_id: str, text: str, metadata: dict):
    collection = get_collection()
    collection.upsert(
        ids=[doc_id],
        documents=[text],
        metadatas=[_flatten_metadata(metadata)],
    )


def query(query_text: str, n_results: int = 8):
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    return collection.query(
        query_texts=[query_text],
        n_results=min(n_results, count),
    )


def get_by_id(doc_id: str):
    collection = get_collection()
    res = collection.get(ids=[doc_id], include=["documents", "metadatas"])
    if not res["ids"]:
        return None
    return {
        "doc_id": res["ids"][0],
        "text": res["documents"][0],
        "metadata": res["metadatas"][0],
    }


def list_all():
    collection = get_collection()
    if collection.count() == 0:
        return []
    res = collection.get(include=["documents", "metadatas"])
    out = []
    for doc_id, text, meta in zip(res["ids"], res["documents"], res["metadatas"]):
        out.append({"doc_id": doc_id, "text": text, "metadata": meta})
    return out


def increment_usage(doc_id: str):
    """Bumps a document's usage_count -- feeds the 'frequency' ranking
    signal (how often the firm actually reaches for this precedent)."""
    record = get_by_id(doc_id)
    if not record:
        return
    meta = dict(record["metadata"])
    meta["usage_count"] = int(meta.get("usage_count", 0)) + 1
    collection = get_collection()
    collection.update(ids=[doc_id], metadatas=[_flatten_metadata(meta)])


def reset():
    client = get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
