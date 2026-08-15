"""
Pydantic schemas shared across the API. Keeping these in one file makes
it easy to see the whole data model at a glance -- which matters here,
since the metadata schema below IS the product (it's the structured
"knowhow" the rest of the system is built on).
"""
from typing import Optional
from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """
    Auto-extracted, per the metadata fields called for in the brief.
    Every field is optional because real-world documents won't always
    yield a clean answer -- an empty field is more honest than a guess,
    and the UI should show "not detected" rather than fabricate one.
    """
    matter_type: Optional[str] = None
    practice_area: Optional[str] = None
    jurisdiction: Optional[str] = None
    industry: Optional[str] = None
    client_type: Optional[str] = None
    transaction_value: Optional[str] = None
    document_date: Optional[str] = None
    responsible_lawyer: Optional[str] = None
    counterparty_type: Optional[str] = None
    document_type: Optional[str] = None
    matter_completed: Optional[bool] = None
    document_executed: Optional[bool] = None
    is_draft_or_model: Optional[str] = None  # "draft" | "model" | "executed" | "unknown"
    version: Optional[str] = None
    partner_approved: Optional[bool] = None
    short_description: Optional[str] = None
    confidentiality: Optional[str] = "internal"  # "public" | "internal" | "restricted"


class DocumentRecord(BaseModel):
    doc_id: str
    filename: str
    metadata: DocumentMetadata
    usage_count: int = 0
    text_preview: str = ""


class IngestResult(BaseModel):
    doc_id: str
    filename: str
    metadata: DocumentMetadata
    status: str  # "ingested" | "error"
    error: Optional[str] = None


class RankingWeights(BaseModel):
    similarity: float = 0.4
    recency: float = 0.15
    frequency: float = 0.15
    partner_approval: float = 0.2
    jurisdiction_match: float = 0.1


class SearchRequest(BaseModel):
    query: str
    jurisdiction_filter: Optional[str] = None
    matter_type_filter: Optional[str] = None
    weights: RankingWeights = Field(default_factory=RankingWeights)
    candidate_pool: int = 8
    keep_top: int = 2
    # No real auth in this MVP -- this stands in for "which ethical wall
    # does the requesting lawyer sit behind". "elevated" can see documents
    # marked confidentiality="restricted"; "standard" cannot.
    viewer_clearance: str = "standard"


class SearchResultItem(BaseModel):
    doc_id: str
    filename: str
    metadata: DocumentMetadata
    score: float
    score_breakdown: dict
    similarity: float
    llm_relevance_reason: Optional[str] = None


class RejectedItem(BaseModel):
    doc_id: str
    filename: str
    metadata: DocumentMetadata
    reason: str


class SearchResponse(BaseModel):
    query: str
    candidates_considered: int
    kept: list[SearchResultItem]           # the strongest precedents, selected for drafting
    other_candidates: list[SearchResultItem]  # surfaced but not selected -- browsable/filterable
    rejected: list[RejectedItem]            # outdated / superseded / not partner-approved, with reasons
    access_restricted: list[RejectedItem]   # blocked by confidentiality + viewer_clearance, not content


class DraftRequest(BaseModel):
    query: str
    doc_ids: list[str]
    instructions: Optional[str] = None


class Citation(BaseModel):
    marker: str        # e.g. "1"
    doc_id: str
    filename: str
    excerpt: str        # short quoted/paraphrased snippet the draft grounded on


class DraftResponse(BaseModel):
    draft_text: str     # contains inline [[n]] markers matching citations
    citations: list[Citation]
    gaps: list[str]      # things the sources didn't cover, flagged instead of invented
