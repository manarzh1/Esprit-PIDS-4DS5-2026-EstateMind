"""
Estate Mind — LangGraph State
══════════════════════════════
État partagé entre tous les nœuds du graphe.
Chaque champ est Optional pour que les nœuds ne remplissent
que ce qui les concerne.
"""
from __future__ import annotations

from typing import Annotated, Any, Optional
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# ─── État global du graphe ────────────────────────────────────────────────────

class EstateMindState(TypedDict):
    # ── Messages (mémoire de conversation) ───────────────────────────────────
    # add_messages est un reducer : chaque nœud APPEND, ne remplace pas
    messages: Annotated[list[BaseMessage], add_messages]

    # ── Routing ───────────────────────────────────────────────────────────────
    # Le supervisor écrit ici la prochaine destination
    next_node: Optional[str]
    # Liste des nœuds déjà exécutés dans ce tour
    visited_nodes: list[str]

    # ── Input utilisateur ─────────────────────────────────────────────────────
    user_query: str
    # Intention détectée par le supervisor
    intent: Optional[str]   # "pipeline" | "analyze" | "market" | "status" | "chat"

    # ── Données pipeline (Collector) ──────────────────────────────────────────
    csv_path: Optional[str]
    cleaned_csv_path: Optional[str]
    collector_report: Optional[dict[str, Any]]

    # ── Données Risk (Trust Scoring) ──────────────────────────────────────────
    risk_report: Optional[dict[str, Any]]
    trust_score: Optional[float]
    trust_level: Optional[str]
    fraud_flags: Optional[list[str]]

    # ── Données Legal (RAG) ───────────────────────────────────────────────────
    legal_report: Optional[dict[str, Any]]
    legal_risk_score: Optional[float]
    legal_risk_level: Optional[str]
    relevant_laws: Optional[list[dict]]
    legal_recommendations: Optional[list[str]]

    # ── Données Market (Vue marché) ───────────────────────────────────────────
    market_report: Optional[dict[str, Any]]

    # ── Annonce unique à analyser ─────────────────────────────────────────────
    listing: Optional[dict[str, Any]]

    # ── Réponse finale ────────────────────────────────────────────────────────
    final_response: Optional[str]

    # ── Erreurs ───────────────────────────────────────────────────────────────
    errors: list[str]
