"""app/models/schemas.py — Schémas Pydantic v2 complets."""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

SupportedLanguage = Literal["en","fr","ar","unknown"]
IntentType = Literal["price_estimation","investment_analysis","location_analysis",
                     "legal_verification","report_generation","general_query","unknown"]
AgentName = Literal["BO1","BO2","BO3","BO4","BO5","orchestrator"]


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=4096,
        examples=["Quel est le prix d'un S+2 à Ariana?"])
    session_id: uuid.UUID | None = None
    user_id: str | None = None
    generate_report: bool = False
    language_override: SupportedLanguage | None = None


class PipelineStep(BaseModel):
    step: int
    name: str
    result: Any = None
    confidence: float | None = None
    ms: int = 0
    details: dict = {}


class NaiveBayesDetail(BaseModel):
    top_features: list[str] = []
    laplace_applied: bool = True
    vocabulary_size: int = 0
    ngram_range: str = "1-3"
    intent_probabilities: dict[str, float] = {}


class ExplanationModel(BaseModel):
    pipeline_steps: list[PipelineStep] = []
    naive_bayes_detail: NaiveBayesDetail = NaiveBayesDetail()
    data_source: str = ""
    hallucination_check: str = "PASSED — 0 données inventées"
    summary: str = ""
    model_used: str = "naive_bayes_ngram_v1"
    caveats: list[str] = []


class ChatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    interaction_id: uuid.UUID
    session_id: uuid.UUID
    response: str
    language: SupportedLanguage
    intent: IntentType
    confidence: float
    intent_probabilities: dict[str, float] = {}
    explanation: ExplanationModel | None = None
    report_url: str | None = None
    processing_ms: int
    agent_used: AgentName
    raw_data: dict | None = None


class InteractionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    interaction_id: uuid.UUID
    session_id: uuid.UUID
    original_query: str
    detected_language: str
    detected_intent: str | None
    response_text: str | None
    confidence_score: float | None
    report_generated: bool
    created_at: datetime


class HistoryResponse(BaseModel):
    session_id: uuid.UUID | None
    total: int
    page: int
    page_size: int
    interactions: list[InteractionSummary]


class ReportCreateRequest(BaseModel):
    session_id: uuid.UUID
    report_type: Literal["price","investment","location","legal","full"] = "full"
    language: SupportedLanguage = "fr"


class ReportResponse(BaseModel):
    report_id: uuid.UUID
    session_id: uuid.UUID
    report_type: str
    download_url: str
    created_at: datetime
    summary: str | None


class PropertySearchRequest(BaseModel):
    query: str = ""
    city: str | None = None
    transaction_type: Literal["vente","location"] | None = None
    property_type: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    min_surface: float | None = None
    max_surface: float | None = None
    bedrooms: int | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PropertyItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source: str
    listing_id: str
    title: str | None
    price_value: float | None
    currency: str | None
    surface_m2: float | None
    bedrooms: float | None
    city: str | None
    district: str | None
    transaction_type: str | None
    property_type: str | None
    url: str | None


class PropertySearchResponse(BaseModel):
    total: int; page: int; page_size: int; items: list[PropertyItem]


class HealthResponse(BaseModel):
    status: Literal["ok","degraded","error"]
    version: str
    environment: str
    database: str
    agents: dict[str, str]
    components: dict[str, str]


class MetricsResponse(BaseModel):
    accuracy: float
    macro_f1: float
    weighted_f1: float
    perplexity: float
    hallucination_rate: float
    darija_coverage: float
    avg_latency_ms: float
    total_interactions: int
    per_class: list[dict]
