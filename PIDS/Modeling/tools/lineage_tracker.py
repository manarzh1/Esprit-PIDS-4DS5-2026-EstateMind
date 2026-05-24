"""
Estate Mind — Data Lineage Tracker
════════════════════════════════════
Trace le cycle de vie complet de chaque annonce, de la collecte à PostgreSQL.

Chaque annonce porte un lineage_chain JSON qui documente :
  - Quelle source l'a collectée (tayara, mubawab...)
  - Si elle a été enrichie par le NLP cleaner (et quels champs)
  - Si elle a été détectée comme quasi-doublon puis fusionnée
  - Chaque transformation appliquée (nettoyage prix, surface, type...)
  - Timestamp de chaque étape
  - Hash de chaque version pour la reproductibilité

Exemple de lineage_chain :
{
  "listing_id": "abc123",
  "created_at": "2026-04-08T10:00:00",
  "steps": [
    {"step": "ingestion",   "source": "tayara",   "ts": "...", "rows_at_step": 847},
    {"step": "nlp_enrich",  "fields_filled": ["price","rooms"], "ts": "..."},
    {"step": "fuzzy_dedup", "action": "kept",     "similarity": null, "ts": "..."},
    {"step": "cleaning",    "transforms": ["price_parsed","surface_parsed"], "ts": "..."},
    {"step": "postgres",    "action": "inserted", "ts": "..."}
  ],
  "data_hash": "a1b2c3d4",
  "pipeline_version": "v2"
}
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Optional

import pandas as pd
from loguru import logger


# ── Noms d'étapes standardisés ────────────────────────────────────────────────

STEP_INGESTION   = "ingestion"
STEP_HEALTH      = "health_check"
STEP_NLP         = "nlp_enrichment"
STEP_FUZZY       = "fuzzy_deduplication"
STEP_CLEANING    = "cleaning"
STEP_TRUST       = "trust_scoring"
STEP_LEGAL       = "legal_scoring"
STEP_POSTGRES    = "postgres_upsert"


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _hash_row(row: dict) -> str:
    """SHA-256 tronqué des champs principaux pour la reproductibilité."""
    key = {k: row.get(k) for k in ["price", "surface", "title", "city", "url"]}
    content = json.dumps(key, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()[:12]


# ── LineageBuilder : construit le lineage d'une annonce ──────────────────────

class LineageBuilder:
    """Construit le lineage_chain d'une annonce étape par étape."""

    def __init__(self, source: str, pipeline_version: str = "v2"):
        self.source           = source
        self.pipeline_version = pipeline_version
        self.steps: list      = []
        self.created_at       = _now()

    def add_step(self, step: str, **kwargs) -> "LineageBuilder":
        """Ajoute une étape au lineage."""
        self.steps.append({"step": step, "ts": _now(), **kwargs})
        return self

    def build(self, row: dict) -> dict:
        """Retourne le lineage_chain complet."""
        return {
            "source":           self.source,
            "created_at":       self.created_at,
            "pipeline_version": self.pipeline_version,
            "data_hash":        _hash_row(row),
            "steps":            self.steps,
        }


# ── LineageTracker : appliqué sur tout le DataFrame ──────────────────────────

class LineageTracker:
    """
    Enrichit un DataFrame avec des colonnes de traçabilité.

    Colonnes ajoutées :
      lineage_chain     : JSON complet du cycle de vie
      lineage_source    : source d'origine
      lineage_steps     : liste des étapes (compact)
      lineage_hash      : hash du contenu pour détection de changements
    """

    def __init__(self, pipeline_version: str = "v2"):
        self.pipeline_version = pipeline_version

    def init_lineage(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Initialise le lineage de toutes les annonces après l'ingestion.
        Appelé juste après ConnectorRegistry.ingest_all().
        """
        df = df.copy()

        def _build(row: pd.Series) -> str:
            source = str(row.get("source", "unknown"))
            chain  = {
                "source":           source,
                "created_at":       _now(),
                "pipeline_version": self.pipeline_version,
                "data_hash":        _hash_row(row.to_dict()),
                "steps": [
                    {
                        "step":   STEP_INGESTION,
                        "source": source,
                        "ts":     _now(),
                    }
                ],
            }
            return json.dumps(chain, ensure_ascii=False)

        df["lineage_chain"]  = df.apply(_build, axis=1)
        df["lineage_source"] = df["source"]
        df["lineage_hash"]   = df.apply(lambda r: _hash_row(r.to_dict()), axis=1)

        logger.info(f"[Lineage] Initialisé pour {len(df)} annonces")
        return df

    def add_step_to_all(
        self,
        df:   pd.DataFrame,
        step: str,
        **step_kwargs,
    ) -> pd.DataFrame:
        """
        Ajoute une étape à toutes les annonces du DataFrame.
        Appelé après chaque transformation du pipeline.
        """
        if "lineage_chain" not in df.columns:
            return df

        df = df.copy()
        new_step = {"step": step, "ts": _now(), **step_kwargs}

        def _append(chain_json: str) -> str:
            try:
                chain = json.loads(chain_json) if isinstance(chain_json, str) else {}
                chain.setdefault("steps", []).append(new_step)
                return json.dumps(chain, ensure_ascii=False)
            except Exception:
                return chain_json

        df["lineage_chain"] = df["lineage_chain"].apply(_append)
        return df

    def add_nlp_step(
        self,
        df:               pd.DataFrame,
        fields_filled:    list[str],
        n_enriched:       int,
        temperature:      float,
    ) -> pd.DataFrame:
        """Trace l'enrichissement NLP."""
        return self.add_step_to_all(
            df, STEP_NLP,
            fields_filled=fields_filled,
            n_enriched=n_enriched,
            temperature=temperature,
        )

    def add_fuzzy_step(
        self,
        df:            pd.DataFrame,
        n_dups_found:  int,
        threshold:     float,
    ) -> pd.DataFrame:
        """Trace la déduplication floue."""
        return self.add_step_to_all(
            df, STEP_FUZZY,
            n_duplicates_removed=n_dups_found,
            threshold=threshold,
            action="kept",
        )

    def add_cleaning_step(
        self,
        df:          pd.DataFrame,
        rows_before: int,
        rows_after:  int,
    ) -> pd.DataFrame:
        """Trace le nettoyage."""
        return self.add_step_to_all(
            df, STEP_CLEANING,
            rows_before=rows_before,
            rows_after=rows_after,
            removed=rows_before - rows_after,
        )

    def add_scoring_step(
        self,
        df:         pd.DataFrame,
        step_name:  str,
        mean_score: float,
    ) -> pd.DataFrame:
        """Trace un scoring (trust ou legal)."""
        return self.add_step_to_all(df, step_name, mean_score=round(mean_score, 3))

    def add_postgres_step(
        self,
        df:       pd.DataFrame,
        inserted: int,
        updated:  int,
        skipped:  int,
    ) -> pd.DataFrame:
        """Trace la sauvegarde PostgreSQL."""
        return self.add_step_to_all(
            df, STEP_POSTGRES,
            inserted=inserted,
            updated=updated,
            skipped=skipped,
        )

    def get_lineage(self, row: pd.Series) -> Optional[dict]:
        """Retourne le lineage d'une annonce spécifique."""
        chain_json = row.get("lineage_chain")
        if not chain_json:
            return None
        try:
            return json.loads(chain_json)
        except Exception:
            return None

    def format_lineage(self, row: pd.Series) -> str:
        """Formate le lineage pour l'affichage."""
        chain = self.get_lineage(row)
        if not chain:
            return "Aucun lineage disponible"
        lines = [
            f"Source  : {chain.get('source', '?')}",
            f"Créé le : {chain.get('created_at', '?')}",
            f"Version : {chain.get('pipeline_version', '?')}",
            f"Hash    : {chain.get('data_hash', '?')}",
            "",
            "Étapes :",
        ]
        for i, step in enumerate(chain.get("steps", []), 1):
            step_name = step.get("step", "?")
            ts        = step.get("ts", "")[:19]
            extras    = {k: v for k, v in step.items() if k not in ("step", "ts")}
            extra_str = " | ".join(f"{k}={v}" for k, v in extras.items())
            lines.append(f"  {i}. [{ts}] {step_name}" + (f" → {extra_str}" if extra_str else ""))
        return "\n".join(lines)

    def get_summary_stats(self, df: pd.DataFrame) -> dict:
        """Statistiques globales du lineage sur le DataFrame complet."""
        if "lineage_chain" not in df.columns:
            return {}

        sources = df.get("lineage_source", pd.Series()).value_counts().to_dict()
        step_counts: dict = {}

        for chain_json in df["lineage_chain"].dropna():
            try:
                chain = json.loads(chain_json)
                for step in chain.get("steps", []):
                    s = step.get("step", "?")
                    step_counts[s] = step_counts.get(s, 0) + 1
            except Exception:
                pass

        return {
            "total_tracked":    len(df),
            "sources":          sources,
            "step_distribution": step_counts,
            "has_nlp":          step_counts.get(STEP_NLP, 0),
            "has_fuzzy_dedup":  step_counts.get(STEP_FUZZY, 0),
            "postgres_inserted": step_counts.get(STEP_POSTGRES, 0),
        }
