"""
Estate Mind — MLflow Tracker
══════════════════════════════
Loggue chaque run du pipeline avec :
  - Hyperparamètres : temperature, chunk_size, dedup_threshold, batch_size...
  - Métriques      : rows_in/out, quality scores, trust score moyen, drift...
  - Artefacts      : CSV nettoyé, rapport de qualité JSON, graphique distribution

Usage :
    tracker = MLflowTracker()
    run_id  = tracker.start_run(config)
    tracker.log_ingestion(rows_in, rows_out, sources)
    tracker.log_quality(quality_report)
    tracker.log_drift(drift_report)
    tracker.end_run(status="success")

Visualiser :
    mlflow ui --backend-store-uri sqlite:///mlflow.db
    → http://localhost:5000
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from loguru import logger

from config.settings import (
    MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT,
    get_hyperparams_dict,
)

try:
    import mlflow
    import mlflow.sklearn
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logger.warning("[MLflow] mlflow non installé — pip install mlflow")


class MLflowTracker:
    """
    Wrapper MLflow pour le pipeline Estate Mind.
    Gère gracieusement l'absence de MLflow (mode no-op).
    """

    def __init__(
        self,
        tracking_uri:    str = MLFLOW_TRACKING_URI,
        experiment_name: str = MLFLOW_EXPERIMENT,
    ):
        self.enabled = MLFLOW_AVAILABLE
        self._run    = None
        self.run_id  = None

        if not self.enabled:
            return

        try:
            mlflow.set_tracking_uri(tracking_uri)
            mlflow.set_experiment(experiment_name)
            logger.info(f"[MLflow] Connecté — URI={tracking_uri}, Exp={experiment_name}")
        except Exception as e:
            logger.warning(f"[MLflow] Initialisation échouée : {e}")
            self.enabled = False

    # ── Cycle de vie d'un run ─────────────────────────────────────────────────

    def start_run(
        self,
        run_name:   Optional[str] = None,
        config:     Optional[dict] = None,
        tags:       Optional[dict] = None,
    ) -> Optional[str]:
        """
        Démarre un run MLflow et loggue tous les hyperparamètres.
        Retourne le run_id (utile pour le logging PostgreSQL).
        """
        if not self.enabled:
            self.run_id = f"local_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            return self.run_id

        try:
            name = run_name or f"pipeline_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            all_tags = {"project": "estate_mind", "bo": "BO1", **(tags or {})}

            self._run   = mlflow.start_run(run_name=name, tags=all_tags)
            self.run_id = self._run.info.run_id

            # Log de TOUS les hyperparamètres
            params = {**get_hyperparams_dict(), **(config or {})}
            # MLflow limite les params à 500 chars par valeur
            safe_params = {k: str(v)[:500] for k, v in params.items()}
            mlflow.log_params(safe_params)

            logger.info(f"[MLflow] Run démarré : {name} (id={self.run_id[:8]}...)")
            return self.run_id

        except Exception as e:
            logger.warning(f"[MLflow] start_run échoué : {e}")
            self.enabled = False
            return None

    def end_run(self, status: str = "FINISHED") -> None:
        if not self.enabled or self._run is None:
            return
        try:
            mlflow.end_run(status=status)
            logger.info(f"[MLflow] Run terminé — status={status}")
        except Exception as e:
            logger.warning(f"[MLflow] end_run échoué : {e}")

    # ── Log des métriques ─────────────────────────────────────────────────────

    def log_ingestion(
        self,
        rows_in:       int,
        rows_out:      int,
        sources_used:  list[str],
        n_duplicates:  int = 0,
    ) -> None:
        """Métriques d'ingestion multi-sources."""
        if not self.enabled: return
        try:
            mlflow.log_metrics({
                "ingestion/rows_in":        rows_in,
                "ingestion/rows_out":       rows_out,
                "ingestion/retention_rate": round(rows_out / max(rows_in, 1), 4),
                "ingestion/duplicates_removed": n_duplicates,
                "ingestion/n_sources":      len(sources_used),
            })
            mlflow.log_param("sources_used", ",".join(sources_used))
            logger.info(f"[MLflow] Ingestion loggée : {rows_in}→{rows_out}")
        except Exception as e:
            logger.warning(f"[MLflow] log_ingestion échoué : {e}")

    def log_quality(self, quality_report: dict) -> None:
        """Score qualité 5 dimensions + score global."""
        if not self.enabled: return
        try:
            metrics = {
                f"quality/{k}": float(v)
                for k, v in quality_report.items()
                if isinstance(v, (int, float))
            }
            mlflow.log_metrics(metrics)

            # Artefact : rapport JSON complet
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as f:
                json.dump(quality_report, f, ensure_ascii=False, indent=2)
                tmp = f.name
            mlflow.log_artifact(tmp, artifact_path="quality")
            os.unlink(tmp)
            logger.info(f"[MLflow] Qualité loggée : score={quality_report.get('global_quality_score')}")
        except Exception as e:
            logger.warning(f"[MLflow] log_quality échoué : {e}")

    def log_trust_scoring(
        self,
        mean_trust:    float,
        fiable_count:  int,
        moyen_count:   int,
        suspect_count: int,
        total:         int,
    ) -> None:
        """Métriques trust scoring."""
        if not self.enabled: return
        try:
            mlflow.log_metrics({
                "trust/mean_score":       round(mean_trust, 4),
                "trust/fiable_pct":       round(fiable_count  / max(total, 1), 4),
                "trust/moyen_pct":        round(moyen_count   / max(total, 1), 4),
                "trust/suspect_pct":      round(suspect_count / max(total, 1), 4),
                "trust/suspect_count":    suspect_count,
            })
        except Exception as e:
            logger.warning(f"[MLflow] log_trust_scoring échoué : {e}")

    def log_nlp_enrichment(
        self,
        n_enriched: int,
        n_total:    int,
        temperature: float,
    ) -> None:
        """Métriques enrichissement NLP."""
        if not self.enabled: return
        try:
            mlflow.log_metrics({
                "nlp/enriched_count": n_enriched,
                "nlp/enriched_pct":   round(n_enriched / max(n_total, 1), 4),
                "nlp/temperature":    temperature,
            })
        except Exception as e:
            logger.warning(f"[MLflow] log_nlp_enrichment échoué : {e}")

    def log_drift(self, drift_report: dict) -> None:
        """Métriques de data drift."""
        if not self.enabled: return
        try:
            metrics = {}
            for col, info in drift_report.get("columns", {}).items():
                if isinstance(info, dict):
                    metrics[f"drift/{col}_ks_stat"]   = float(info.get("ks_statistic", 0))
                    metrics[f"drift/{col}_drifted"]   = float(info.get("drifted", False))
            metrics["drift/n_drifted_cols"] = float(drift_report.get("n_drifted_columns", 0))
            metrics["drift/global_drifted"]  = float(drift_report.get("global_drift", False))
            mlflow.log_metrics(metrics)
            logger.info(f"[MLflow] Drift loggé : {drift_report.get('n_drifted_columns', 0)} colonnes driftées")
        except Exception as e:
            logger.warning(f"[MLflow] log_drift échoué : {e}")

    def log_source_health(self, health_report: dict) -> None:
        """Métriques de santé des sources."""
        if not self.enabled: return
        try:
            for source, info in health_report.get("sources", {}).items():
                if isinstance(info, dict):
                    mlflow.log_metrics({
                        f"health/{source}_status": float(info.get("healthy", False)),
                        f"health/{source}_rows":   float(info.get("rows", 0)),
                    })
        except Exception as e:
            logger.warning(f"[MLflow] log_source_health échoué : {e}")

    def log_csv_artifact(self, csv_path: str, name: str = "listings_clean") -> None:
        """Loggue le CSV nettoyé comme artefact versionné."""
        if not self.enabled: return
        try:
            if Path(csv_path).exists():
                mlflow.log_artifact(csv_path, artifact_path=f"datasets/{name}")
                logger.info(f"[MLflow] Artefact CSV loggué : {csv_path}")
        except Exception as e:
            logger.warning(f"[MLflow] log_csv_artifact échoué : {e}")

    def log_price_distribution_chart(self, df: pd.DataFrame) -> None:
        """Génère et loggue un graphique de distribution des prix."""
        if not self.enabled: return
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(1, 2, figsize=(12, 4))
            fig.suptitle("Distribution des prix — Estate Mind", fontsize=12)

            if "price" in df.columns:
                prices = df["price"].dropna()
                axes[0].hist(prices, bins=50, color="#1D9E75", alpha=0.8, edgecolor="none")
                axes[0].set_title("Distribution des prix (TND)")
                axes[0].set_xlabel("Prix TND")
                axes[0].set_ylabel("Nb annonces")

            if "price_per_m2" in df.columns:
                ppm2 = df["price_per_m2"].dropna()
                axes[1].hist(ppm2, bins=50, color="#7F77DD", alpha=0.8, edgecolor="none")
                axes[1].set_title("Distribution prix/m² (TND/m²)")
                axes[1].set_xlabel("TND/m²")

            plt.tight_layout()

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                plt.savefig(f.name, dpi=120, bbox_inches="tight")
                tmp = f.name
            plt.close()

            mlflow.log_artifact(tmp, artifact_path="charts")
            os.unlink(tmp)
            logger.info("[MLflow] Graphique distribution des prix loggué")
        except Exception as e:
            logger.warning(f"[MLflow] log_price_distribution_chart échoué : {e}")

    def get_best_run(self, metric: str = "quality/global_quality_score") -> Optional[dict]:
        """Retourne le meilleur run selon une métrique."""
        if not self.enabled: return None
        try:
            client = mlflow.tracking.MlflowClient()
            exp    = client.get_experiment_by_name(MLFLOW_EXPERIMENT)
            if exp is None: return None
            runs   = client.search_runs(
                experiment_ids=[exp.experiment_id],
                order_by=[f"metrics.{metric} DESC"],
                max_results=1,
            )
            if runs:
                r = runs[0]
                return {
                    "run_id": r.info.run_id,
                    "metric": r.data.metrics.get(metric),
                    "params": r.data.params,
                    "start":  r.info.start_time,
                }
        except Exception as e:
            logger.warning(f"[MLflow] get_best_run échoué : {e}")
        return None
