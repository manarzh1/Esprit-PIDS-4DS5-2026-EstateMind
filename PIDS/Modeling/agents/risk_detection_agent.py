"""
Estate Mind — Risk Detection Agent (Agent 3 / Priorité ③)
──────────────────────────────────────────────────────────
Responsabilités :
  - Calculer un trust_score [0-1] par annonce
  - Détecter les fraudes et anomalies
  - Identifier les quasi-doublons cross-plateformes
  - Générer des alertes sur les listings suspects
  - Enrichir le CSV avec les scores de confiance

Architecture : LangChain Tool-calling Agent
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from loguru import logger

from config.settings import (
    LLM_MODEL, OPENAI_API_KEY, PROC_DIR, TRUST_SCORE_THRESHOLD
)
from tools.risk_tools import (
    compute_trust_score,
    get_fraud_flags,
    get_suspicious_listings,
    run_trust_scoring,
)


# ─── LangChain Tools ──────────────────────────────────────────────────────────

@tool
def score_single_listing(
    price: float,
    surface: float,
    city: str,
    description: str,
    source: str,
    property_type: str = "appartement",
) -> str:
    """
    Calcule le trust_score d'une annonce unique et retourne l'analyse détaillée.
    """
    try:
        logger.info("===================================================")
        logger.info("[RiskDetectionAgent] 🔍 ANALYSE D'UNE ANNONCE UNIQUE")
        logger.info(f"[RiskDetectionAgent] Ville={city}, Type={property_type}, Source={source}")

        row = pd.Series({
            "price": price,
            "surface": surface,
            "city": city,
            "description": description,
            "source": source,
            "property_type": property_type,
        })

        df_ref = pd.DataFrame([row.to_dict()])

        score = compute_trust_score(row, df_ref)
        flags = get_fraud_flags(row, df_ref)

        level = (
            "Fiable" if score >= 0.75 else
            "Moyen" if score >= 0.50 else
            "Suspect"
        )

        logger.info(f"[RiskDetectionAgent] 📊 Trust score : {score}")
        logger.info(f"[RiskDetectionAgent] 🏷️ Niveau : {level}")
        logger.info(f"[RiskDetectionAgent] 🚨 Flags : {flags if flags else 'aucun'}")
        logger.info("[RiskDetectionAgent] ✅ ANALYSE TERMINÉE")
        logger.info("===================================================")

        return json.dumps({
            "trust_score": score,
            "trust_level": level,
            "fraud_flags": flags,
            "recommendation": (
                "Annonce fiable — procéder normalement" if score >= 0.75 else
                "Vérifications recommandées avant décision" if score >= 0.50 else
                "Annonce suspecte — investigation requise"
            ),
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"[RiskDetectionAgent] ❌ Erreur analyse unique : {e}")
        return json.dumps({"error": str(e)})


@tool
def batch_trust_scoring(cleaned_csv_path: str) -> str:
    """
    Applique le trust scoring sur l'ensemble du dataset nettoyé.
    """
    try:
        logger.info("===================================================")
        logger.info("[RiskDetectionAgent] 🚀 TRUST SCORING GLOBAL")
        logger.info(f"[RiskDetectionAgent] Dataset : {cleaned_csv_path}")

        df = pd.read_csv(cleaned_csv_path)
        logger.info(f"[RiskDetectionAgent] 📥 Lignes à scorer : {len(df)}")

        df = run_trust_scoring(df)
        df.to_csv(cleaned_csv_path, index=False)

        suspicious = get_suspicious_listings(df, threshold=TRUST_SCORE_THRESHOLD)
        top_suspect = suspicious.head(5)[
            ["title", "price", "surface", "city", "source", "trust_score"]
        ].to_dict(orient="records")

        mean_score = round(df["trust_score"].mean(), 3)
        fiable_count = int((df["trust_score"] >= 0.75).sum())
        moyen_count = int(((df["trust_score"] >= 0.50) & (df["trust_score"] < 0.75)).sum())
        suspect_count = int((df["trust_score"] < 0.50).sum())

        logger.info(f"[RiskDetectionAgent] 📊 Score moyen : {mean_score}")
        logger.info(f"[RiskDetectionAgent] ✅ Fiables : {fiable_count}")
        logger.info(f"[RiskDetectionAgent] ⚠️ Moyens : {moyen_count}")
        logger.info(f"[RiskDetectionAgent] 🚨 Suspects : {suspect_count}")
        logger.info("[RiskDetectionAgent] ✅ TRUST SCORING TERMINÉ")
        logger.info("===================================================")

        return json.dumps({
            "total_listings": len(df),
            "mean_trust_score": mean_score,
            "fiable_count": fiable_count,
            "moyen_count": moyen_count,
            "suspect_count": suspect_count,
            "top_suspects": top_suspect,
            "output_path": cleaned_csv_path,
        }, ensure_ascii=False, default=str)

    except Exception as e:
        logger.error(f"[RiskDetectionAgent] ❌ Erreur batch scoring : {e}")
        return json.dumps({"error": str(e)})


@tool
def detect_cross_platform_duplicates(cleaned_csv_path: str) -> str:
    """
    Détecte les annonces dupliquées entre plateformes.
    """
    try:
        logger.info("===================================================")
        logger.info("[RiskDetectionAgent] 🔁 DÉTECTION DE DOUBLONS CROSS-PLATFORM")
        logger.info(f"[RiskDetectionAgent] Dataset : {cleaned_csv_path}")

        df = pd.read_csv(cleaned_csv_path)

        groups = df.groupby(
            ["price", "surface", "city"],
            dropna=True
        ).filter(lambda g: len(g) > 1 and g["source"].nunique() > 1)

        n_groups = groups.groupby(["price", "surface", "city"]).ngroups

        examples = (
            groups.groupby(["price", "surface", "city"])
            .apply(lambda g: g[["source", "title", "price", "surface", "city"]].to_dict(orient="records"))
            .head(3)
            .to_dict()
        )

        logger.info(f"[RiskDetectionAgent] 🔁 Groupes détectés : {n_groups}")
        logger.info(f"[RiskDetectionAgent] 📌 Annonces concernées : {len(groups)}")
        logger.info("[RiskDetectionAgent] ✅ DÉTECTION TERMINÉE")
        logger.info("===================================================")

        return json.dumps({
            "duplicate_groups": n_groups,
            "affected_listings": len(groups),
            "pct_duplicated": round(len(groups) / len(df) * 100, 2),
            "examples": str(examples)[:500],
        }, ensure_ascii=False, default=str)

    except Exception as e:
        logger.error(f"[RiskDetectionAgent] ❌ Erreur doublons : {e}")
        return json.dumps({"error": str(e)})


@tool
def generate_fraud_report(cleaned_csv_path: str) -> str:
    """
    Génère un rapport de fraude complet.
    """
    try:
        logger.info("===================================================")
        logger.info("[RiskDetectionAgent] 🕵️ GÉNÉRATION DU RAPPORT FRAUDE")
        logger.info(f"[RiskDetectionAgent] Dataset : {cleaned_csv_path}")

        df = pd.read_csv(cleaned_csv_path)

        if "trust_score" not in df.columns:
            df = run_trust_scoring(df)

        suspect_df = get_suspicious_listings(df, threshold=TRUST_SCORE_THRESHOLD)

        fraud_cases = []
        for _, row in suspect_df.head(20).iterrows():
            flags = get_fraud_flags(row, df)
            fraud_cases.append({
                "title": str(row.get("title", ""))[:80],
                "city": str(row.get("city", "")),
                "price": row.get("price"),
                "trust_score": row.get("trust_score"),
                "source": str(row.get("source", "")),
                "flags": flags,
            })

        pct_suspect = round(len(suspect_df) / len(df) * 100, 1)

        logger.info(f"[RiskDetectionAgent] 🚨 Cas suspects : {len(suspect_df)}")
        logger.info(f"[RiskDetectionAgent] 📉 Pourcentage suspect : {pct_suspect}%")
        logger.info("[RiskDetectionAgent] ✅ RAPPORT FRAUDE TERMINÉ")
        logger.info("===================================================")

        return json.dumps({
            "total_suspect": len(suspect_df),
            "pct_suspect": pct_suspect,
            "fraud_cases": fraud_cases,
            "threshold_used": TRUST_SCORE_THRESHOLD,
            "recommendation": (
                "Dataset propre — risque faible" if len(suspect_df) < len(df) * 0.05 else
                "Quelques anomalies détectées" if len(suspect_df) < len(df) * 0.15 else
                "Volume élevé d'annonces suspectes — nettoyage supplémentaire requis"
            ),
        }, ensure_ascii=False, default=str)

    except Exception as e:
        logger.error(f"[RiskDetectionAgent] ❌ Erreur rapport fraude : {e}")
        return json.dumps({"error": str(e)})


# ─── Prompt système du Risk Detection Agent ────────────────────────────────────

RISK_SYSTEM_PROMPT = """Tu es le Risk Detection Agent d'Estate Mind.

Tu analyses les annonces immobilières tunisiennes pour détecter :
  🔴 Fraudes : prix anormaux, descriptions suspectes, paiement cash exigé
  🟡 Anomalies : données manquantes critiques, quasi-doublons cross-plateformes
  🟢 Annonces fiables : données complètes, prix cohérents, sources professionnelles

Tu calcules un trust_score [0-1] pour chaque annonce :
  ≥ 0.75 → Fiable
  0.50 - 0.75 → Moyen (vérifications recommandées)
  < 0.50 → Suspect (investigation requise)

Le score est composé de 5 dimensions :
  - Cohérence du prix vs le marché local (30%)
  - Qualité de la description (20%)
  - Complétude des données (25%)
  - Fiabilité de la source (15%)
  - Risque de duplication (10%)

Pour chaque analyse :
  - Explique les facteurs qui font baisser/monter le score
  - Cite les signaux d'alerte spécifiques (fraud_flags)
  - Recommande une action (procéder / vérifier / investiguer)

Langue : français.
"""


# ─── Risk Detection Agent Factory ─────────────────────────────────────────────

def create_risk_agent(verbose: bool = True) -> AgentExecutor:
    """Crée et retourne l'AgentExecutor du Risk Detection Agent."""
    llm = ChatOpenAI(
        model=LLM_MODEL,
        temperature=0,
        api_key=OPENAI_API_KEY,
    )

    tools = [
        score_single_listing,
        batch_trust_scoring,
        detect_cross_platform_duplicates,
        generate_fraud_report,
    ]

    prompt = ChatPromptTemplate.from_messages([
        ("system", RISK_SYSTEM_PROMPT),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)

    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=verbose,
        handle_parsing_errors=True,
        max_iterations=8,
        return_intermediate_steps=True,
    )


# ─── Interface haut-niveau ────────────────────────────────────────────────────

class RiskDetectionAgent:
    """
    Interface haut-niveau pour le Risk Detection Agent.
    Utilisée par le Master Orchestrator.
    """

    def __init__(self, verbose: bool = False):
        self.executor = create_risk_agent(verbose=verbose)
        self.name = "RiskDetectionAgent"

    def score_listing(self, listing: dict) -> dict:
        """Score une annonce unique."""
        logger.info("===================================================")
        logger.info("[RiskDetectionAgent] 🤖 MODE LLM - SCORE UNIQUE")
        logger.info(f"[RiskDetectionAgent] Ville : {listing.get('city', '')}")

        result = self.executor.invoke({
            "input": (
                f"Calcule le trust_score de cette annonce et explique le résultat :\n"
                f"{listing}"
            )
        })

        logger.info("[RiskDetectionAgent] ✅ EXÉCUTION LLM TERMINÉE")
        logger.info("===================================================")
        return {"agent": self.name, "output": result.get("output", "")}

    def process_full_dataset(self, cleaned_csv_path: str) -> dict:
        """Trust scoring + détection doublons + rapport fraude sur le CSV complet."""
        logger.info("===================================================")
        logger.info("[RiskDetectionAgent] 🤖 MODE LLM - DATASET COMPLET")
        logger.info(f"[RiskDetectionAgent] Dataset : {cleaned_csv_path}")

        result = self.executor.invoke({
            "input": (
                f"Traite le fichier '{cleaned_csv_path}' : "
                f"1) Applique le trust scoring sur toutes les annonces. "
                f"2) Détecte les doublons cross-plateformes. "
                f"3) Génère le rapport de fraude. "
                f"Résume les résultats clés."
            )
        })

        logger.info("[RiskDetectionAgent] ✅ EXÉCUTION LLM TERMINÉE")
        logger.info("===================================================")
        return {"agent": self.name, "output": result.get("output", "")}

    def run_without_llm(self, cleaned_csv_path: str) -> pd.DataFrame:
        """Mode rapide sans LLM : trust scoring direct."""
        logger.info("===================================================")
        logger.info("[RiskDetectionAgent] 🚀 DÉMARRAGE TRUST SCORING")
        logger.info(f"[RiskDetectionAgent] Dataset : {cleaned_csv_path}")

        df = pd.read_csv(cleaned_csv_path)
        logger.info(f"[RiskDetectionAgent] 📥 Lignes : {len(df)}")

        df = run_trust_scoring(df)

        mean_score = df["trust_score"].mean()
        suspect_count = (df["trust_score"] < 0.5).sum()

        df.to_csv(cleaned_csv_path, index=False)

        logger.info(f"[RiskDetectionAgent] 📊 Score moyen : {mean_score:.3f}")
        logger.info(f"[RiskDetectionAgent] 🚨 Annonces suspectes : {suspect_count}")
        logger.info("[RiskDetectionAgent] ✅ TRUST SCORING TERMINÉ")
        logger.info("===================================================")

        return df


# ─── Run direct ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    csv = sys.argv[1] if len(sys.argv) > 1 else "data/processed/listings_clean.csv"

    agent = RiskDetectionAgent(verbose=False)
    df = agent.run_without_llm(csv)

    summary = {
    "mean": float(df["trust_score"].mean()),
    "median": float(df["trust_score"].median()),
    "fiable": int((df["trust_score"] > 0.8).sum()),
    "moyen": int(((df["trust_score"] >= 0.5) & (df["trust_score"] <= 0.8)).sum()),
    "suspect": int((df["trust_score"] < 0.5).sum()),
}