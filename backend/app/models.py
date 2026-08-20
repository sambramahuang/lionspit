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
    client_name: Optional[str] = None
    counterparty_name: Optional[str] = None
    matter_reference: Optional[str] = None
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
    status: Optional[str] = None  # "In force" | "Repealed" | "Amending/ overruled"
    matter_completed: Optional[bool] = None
    document_executed: Optional[bool] = None
    is_draft_or_model: Optional[str] = None  # "draft" | "model" | "executed" | "unknown"
    version: Optional[str] = None
    partner_approved: Optional[bool] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    approval_note: Optional[str] = None
    short_description: Optional[str] = None
    confidentiality: Optional[str] = "internal"  # "public" | "internal" | "restricted"


class DocumentRecord(BaseModel):
    doc_id: str
    filename: str
    metadata: DocumentMetadata
    usage_count: int = 0
    text_preview: str = ""


class DocumentApprovalRequest(BaseModel):
    approved: bool
    note: str | None = None


class ExtractedTextResponse(BaseModel):
    filename: str
    text: str


class IngestResult(BaseModel):
    doc_id: str
    filename: str
    metadata: DocumentMetadata
    status: str  # "ingested" | "error"
    error: str | None = None
    conflict_warnings: list[str] = Field(default_factory=list)


class RankingWeights(BaseModel):
    similarity: float = 0.4
    recency: float = 0.15
    frequency: float = 0.15
    partner_approval: float = 0.2
    jurisdiction_match: float = 0.1


class SearchRequest(BaseModel):
    query: str
    jurisdiction_filter: str | None = None
    matter_type_filter: str | None = None
    recency_filter: str | None = None
    status_filters: list[str] = Field(default_factory=list)
    document_type_filters: list[str] = Field(default_factory=list)
    weights: RankingWeights = Field(default_factory=RankingWeights)
    # Raw nearest-neighbor pool pulled before wall-filtering/ranking/
    # supersession runs -- has to be generous enough to reliably contain
    # every document in a query's true matter cluster (so supersession can
    # compare them against each other at all), not just the single closest
    # match. At 8 the correct, partner-approved precedent for the corpus's
    # own flagship "shareholders agreement" query ranked 14th by raw
    # embedding similarity -- below its own earlier drafts/redlines and a
    # deliberately-planted stale duplicate -- and never reached scoring.
    candidate_pool: int = 20
    keep_top: int = 2


class SearchResultItem(BaseModel):
    doc_id: str
    filename: str
    metadata: DocumentMetadata
    score: float
    score_breakdown: dict
    similarity: float
    llm_relevance_reason: str | None = None


class RejectedItem(BaseModel):
    doc_id: str
    filename: str
    metadata: DocumentMetadata
    reason: str


class SearchResponse(BaseModel):
    query: str
    candidates_considered: int
    kept: list[SearchResultItem]  # the strongest precedents, selected for drafting
    other_candidates: list[
        SearchResultItem
    ]  # surfaced but not selected -- browsable/filterable
    rejected: list[
        RejectedItem
    ]  # outdated / superseded / not partner-approved, with reasons
    access_restricted: list[
        RejectedItem
    ]  # blocked by a matter-level ethical wall, not content


class ClauseSearchRequest(BaseModel):
    query: str
    candidate_pool: int = 20
    keep_top: int = 8
    weights: RankingWeights = Field(default_factory=RankingWeights)


class ClauseResult(BaseModel):
    doc_id: str
    filename: str
    clause_index: int
    label: str | None = None
    text: str
    similarity: float
    metadata: DocumentMetadata


class ClauseAccessRestricted(BaseModel):
    doc_id: str
    filename: str
    reason: str


class ClauseSearchResponse(BaseModel):
    query: str
    candidates_considered: int
    kept: list[ClauseResult]
    access_restricted: list[ClauseAccessRestricted]


class LineageNode(BaseModel):
    doc_id: str
    filename: str
    metadata: DocumentMetadata


class LineageEdge(BaseModel):
    from_doc_id: str  # the older / superseded document
    to_doc_id: str  # the current document it points to
    reason: str
    relation: str = "version"  # "version" or "related"


class LineageCluster(BaseModel):
    key: str
    label: str
    current_doc_id: str
    nodes: list[LineageNode]
    edges: list[LineageEdge]


class LineageResponse(BaseModel):
    clusters: list[LineageCluster]
    standalone: list[
        LineageNode
    ]  # documents with no other version in their matter cluster


class MeResponse(BaseModel):
    email: str
    is_partner: bool


class MatterWallInfo(BaseModel):
    matter_key: str
    walled: bool = False
    allowed_emails: list[str] = Field(default_factory=list)
    updated_by: str | None = None
    updated_at: str | None = None


class MatterWallRequest(BaseModel):
    walled: bool
    allowed_emails: list[str] = Field(default_factory=list)


class ConflictFlag(BaseModel):
    matter_key: str
    reason: str
    flagged_doc_id: str | None = None
    detected_at: str | None = None
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: str | None = None


class MatterSummary(BaseModel):
    matter_key: str
    label: str
    document_count: int
    wall: MatterWallInfo
    conflict: ConflictFlag | None = None


class DraftRequest(BaseModel):
    query: str
    doc_ids: list[str]
    instructions: str | None = None


class Citation(BaseModel):
    marker: str  # e.g. "1"
    doc_id: str
    filename: str
    excerpt: str  # short quoted/paraphrased snippet the draft grounded on


class DraftResponse(BaseModel):
    draft_text: str  # contains inline [[n]] markers matching citations
    citations: list[Citation]
    gaps: list[str]  # things the sources didn't cover, flagged instead of invented
