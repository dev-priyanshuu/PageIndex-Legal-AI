from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RetrieverMode = Literal["tree", "vector"]
ExecutionMode = Literal["sequential", "graph"]
LlmProvider = Literal["mock", "gemini"]
TreeGenMode = Literal["auto", "pageindex", "local"]


class IngestRequest(BaseModel):
    document_id: str = Field(..., description="Unique id for the legal document version.")
    title: str
    text: str = Field(..., description="Markdown-like legal text with headings.")
    metadata: dict[str, str] = Field(default_factory=dict)


class IngestPdfResponse(BaseModel):
    document_id: str
    extracted_chars: int
    node_count: int
    tree_generation_mode: str
    message: str


class IngestResponse(BaseModel):
    document_id: str
    node_count: int
    message: str


class AskRequest(BaseModel):
    document_id: str
    question: str
    retriever_mode: RetrieverMode = "tree"
    execution_mode: ExecutionMode = "graph"
    llm_provider: LlmProvider = "mock"
    llm_model: str | None = None
    session_id: str = "default-session"
    top_k: int = 4


RiskSeverity = Literal["critical", "high", "medium", "low"]
PartyAdvantage = Literal["buyer", "seller", "balanced", "unclear"]


class Evidence(BaseModel):
    node_id: str
    heading_path: str
    excerpt: str
    score: float


class RiskItem(BaseModel):
    category: str
    severity: RiskSeverity
    description: str
    clause_reference: str = ""
    affected_party: str = ""
    interacts_with: list[str] = Field(default_factory=list)


class ClauseTension(BaseModel):
    tension_type: str
    source_clause: str
    target_clause: str
    description: str
    severity: str


class NegotiationPoint(BaseModel):
    issue: str
    suggestion: str
    fallback_position: str = ""


class PartyAnalysis(BaseModel):
    advantage: PartyAdvantage
    buyer_protections: list[str]
    seller_protections: list[str]
    summary: str


class RiskScenario(BaseModel):
    risk_category: str
    severity: str
    probability: float
    probability_label: str
    financial_impact_multiple: float
    financial_impact_label: str
    worst_case: str
    mitigation_suggestion: str
    residual_risk_after_mitigation: float
    affected_party: str


class JurisdictionInfo(BaseModel):
    detected_jurisdiction: str
    profile_name: str
    jurisdiction_notes: list[str]
    severity_adjustments: list[dict] = Field(default_factory=list)
    missing_mandatory_provisions: list[str] = Field(default_factory=list)
    jurisdiction_risks: list[dict] = Field(default_factory=list)
    cure_period_gap: bool = False
    termination_notice_gap: bool = False


class AskResponse(BaseModel):
    answer: str
    confidence: float
    reasoning_trace: list[str]
    evidences: list[Evidence]
    risks: list[RiskItem]
    suggestions: list[NegotiationPoint]
    party_analysis: PartyAnalysis
    clause_tensions: list[ClauseTension] = Field(default_factory=list)
    risk_score: float = 0.0
    risk_scenarios: list[RiskScenario] = Field(default_factory=list)
    portfolio_risk: dict = Field(default_factory=dict)
    jurisdiction_info: JurisdictionInfo | None = None
    execution_mode: ExecutionMode
    llm_provider: LlmProvider
    llm_model_used: str


class BenchmarkRequest(BaseModel):
    document_id: str
    top_k: int = 4


class RetrieverMetrics(BaseModel):
    recall_at_k: float
    citation_path_accuracy: float
    risk_detection_accuracy: float


class BenchmarkResponse(BaseModel):
    document_id: str
    tree: RetrieverMetrics
    vector: RetrieverMetrics
    eval_case_coverage: float
    winner: str
    summary: str


class EvaluationReportResponse(BaseModel):
    document_id: str
    markdown_report: str


# ── Tree visualisation ────────────────────────────────────────────────────────

class TreeNodeResponse(BaseModel):
    node_id: str
    title: str
    level: int
    parent_id: str | None
    content_preview: str        # first 300 chars of content
    content_length: int         # total char count
    children: list[str]         # child node_ids
    heading_path: str           # full breadcrumb e.g. "Agreement > Warranty > Disclaimer"
    metadata: dict[str, str]


class DocumentTreeResponse(BaseModel):
    document_id: str
    title: str
    node_count: int
    max_depth: int
    root_ids: list[str]
    nodes: dict[str, TreeNodeResponse]  # node_id → node
    metadata: dict[str, str]

