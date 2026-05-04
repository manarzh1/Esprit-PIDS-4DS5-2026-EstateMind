"""
Estate Mind — monitoring_tools.py
===================================
Outils de monitoring de la qualité des données — VERSION LOCALE.
Tout en fichiers JSON/SQLite, zéro dépendance externe.

Contient :
  - SourceHealthMonitor  : santé des scrapers
  - DriftDetector        : détection de drift statistique
  - PipelineReporter     : rapport global du pipeline

Usage :
    python tools/monitoring_tools.py data/raw/annonces_combined.csv
"""

from __future__ import annotations
import json
import sys
import os
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from scipy import stats

warnings.filterwarnings("ignore")

MONITORING_DIR = Path(__file__).parent.parent / "data" / "monitoring"
MONITORING_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SOURCE HEALTH MONITOR
# ═══════════════════════════════════════════════════════════════════════════════

class SourceHealthMonitor:
    """
    Monitore la santé de chaque source de scraping.
    Détecte les anomalies : trop peu d'annonces, prix dégradés, GPS manquant.
    """

    EXPECTED_MIN = {"mubawab": 100, "tayara": 100, "tecnocasa": 20, "remax": 10}
    EXPECTED_GPS = {"mubawab": 0.60, "tayara": 0.30, "tecnocasa": 0.70, "remax": 0.80}

    def __init__(self, history_path: Path = MONITORING_DIR / "source_health.json"):
        self.history_path = history_path
        self.history: list = self._load_history()

    def _load_history(self) -> list:
        if self.history_path.exists():
            with open(self.history_path) as f:
                return json.load(f)
        return []

    def _save_history(self):
        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(self.history[-100:], f, indent=2, ensure_ascii=False)

    def check(self, df: pd.DataFrame) -> dict:
        """Analyse la santé de chaque source dans le DataFrame."""
        report = {"timestamp": datetime.now().isoformat(), "sources": {}, "alerts": []}

        for source in df["source"].unique():
            sdf  = df[df["source"] == source]
            n    = len(sdf)
            gps  = float(sdf["latitude"].notna().mean()) if "latitude" in sdf else 0.0
            price_null = float(sdf["price_value"].isna().mean()) if "price_value" in sdf else 0.0

            health = {
                "n_annonces":      n,
                "gps_rate":        round(gps, 3),
                "price_null_rate": round(price_null, 3),
                "status":          "ok",
                "alerts":          [],
            }

            # Vérifications
            min_expected = self.EXPECTED_MIN.get(source, 10)
            if n < min_expected:
                msg = f"⚠️  {source}: seulement {n} annonces (attendu ≥ {min_expected})"
                health["alerts"].append(msg)
                health["status"] = "degraded"
                report["alerts"].append(msg)

            gps_expected = self.EXPECTED_GPS.get(source, 0.3)
            if gps < gps_expected - 0.15:
                msg = f"⚠️  {source}: GPS rate={gps:.2f} (attendu ≥ {gps_expected:.2f})"
                health["alerts"].append(msg)
                health["status"] = "degraded"

            if price_null > 0.20:
                msg = f"⚠️  {source}: {price_null:.0%} de prix manquants"
                health["alerts"].append(msg)
                health["status"] = "degraded"

            report["sources"][source] = health

        # Score global
        n_ok = sum(1 for s in report["sources"].values() if s["status"] == "ok")
        n_total = len(report["sources"])
        report["global_health_score"] = round(n_ok / max(n_total, 1), 3)
        report["n_alerts"] = len(report["alerts"])

        self.history.append(report)
        self._save_history()
        return report

    def get_trend(self, source: str, metric: str = "n_annonces") -> list:
        """Retourne l'historique d'une métrique pour une source."""
        return [
            {"ts": r["timestamp"],
             "value": r["sources"].get(source, {}).get(metric)}
            for r in self.history
            if source in r.get("sources", {})
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DRIFT DETECTOR
# ═══════════════════════════════════════════════════════════════════════════════

class DriftDetector:
    """
    Détecte si la distribution des données d'entrée a changé
    par rapport à la distribution de référence (au moment de l'entraînement).

    Utilise le test de Kolmogorov-Smirnov (KS test).
    """

    MONITORED_FEATURES = ["price_value", "surface_m2", "price_per_m2"]
    DRIFT_THRESHOLD    = 0.05  # p-value KS test

    def __init__(self,
                 reference_path: Path = MONITORING_DIR / "drift_reference.json",
                 history_path:   Path = MONITORING_DIR / "drift_history.json"):
        self.ref_path  = reference_path
        self.hist_path = history_path
        self.reference: dict = self._load_reference()

    def _load_reference(self) -> dict:
        if self.ref_path.exists():
            with open(self.ref_path) as f:
                return json.load(f)
        return {}

    def save_reference(self, df: pd.DataFrame):
        """Sauvegarde la distribution de référence (à appeler après entraînement)."""
        ref = {"timestamp": datetime.now().isoformat(), "features": {}}
        for feat in self.MONITORED_FEATURES:
            if feat in df.columns:
                vals = df[feat].dropna()
                ref["features"][feat] = {
                    "mean":  round(float(vals.mean()), 2),
                    "std":   round(float(vals.std()), 2),
                    "p25":   round(float(vals.quantile(0.25)), 2),
                    "p50":   round(float(vals.median()), 2),
                    "p75":   round(float(vals.quantile(0.75)), 2),
                    "n":     len(vals),
                    "sample": vals.sample(min(500, len(vals)),
                                          random_state=42).tolist(),
                }
        with open(self.ref_path, "w") as f:
            json.dump(ref, f, indent=2)
        self.reference = ref
        print(f"   [DriftDetector] Référence sauvegardée → {self.ref_path}")

    def check_drift(self, df: pd.DataFrame) -> dict:
        """Vérifie si la distribution actuelle a dérivé."""
        if not self.reference:
            return {"status": "no_reference",
                    "message": "Appelez save_reference() d'abord",
                    "drifted_features": []}

        result = {
            "timestamp": datetime.now().isoformat(),
            "drifted_features": [],
            "stable_features":  [],
            "feature_details":  {},
        }

        for feat in self.MONITORED_FEATURES:
            if feat not in df.columns or feat not in self.reference.get("features", {}):
                continue

            ref_sample  = self.reference["features"][feat]["sample"]
            curr_sample = df[feat].dropna().sample(
                min(500, len(df[feat].dropna())), random_state=42
            ).tolist()

            ks_stat, p_value = stats.ks_2samp(ref_sample, curr_sample)

            ref_mean  = self.reference["features"][feat]["mean"]
            curr_mean = float(df[feat].dropna().mean())
            mean_shift_pct = abs(curr_mean - ref_mean) / (ref_mean + 1e-9) * 100

            drifted = p_value < self.DRIFT_THRESHOLD or mean_shift_pct > 20

            detail = {
                "ks_stat":        round(float(ks_stat), 4),
                "p_value":        round(float(p_value), 4),
                "drifted":        drifted,
                "ref_mean":       round(ref_mean, 2),
                "curr_mean":      round(curr_mean, 2),
                "mean_shift_pct": round(mean_shift_pct, 1),
            }
            result["feature_details"][feat] = detail

            if drifted:
                result["drifted_features"].append(feat)
            else:
                result["stable_features"].append(feat)

        result["drift_detected"] = len(result["drifted_features"]) > 0
        result["recommendation"] = (
            "⚠️  Ré-entraîner les modèles : drift détecté sur "
            f"{', '.join(result['drifted_features'])}"
            if result["drift_detected"]
            else "✅ Distributions stables — pas de ré-entraînement nécessaire"
        )

        # Sauvegarder l'historique
        history = []
        if self.hist_path.exists():
            with open(self.hist_path) as f:
                history = json.load(f)
        history.append(result)
        with open(self.hist_path, "w") as f:
            json.dump(history[-50:], f, indent=2)

        return result


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PIPELINE REPORTER
# ═══════════════════════════════════════════════════════════════════════════════

class PipelineReporter:
    """
    Génère un rapport global du pipeline Estate Mind.
    Combine : santé des sources + drift + trust scores + anomalies.
    """

    def __init__(self, report_dir: Path = MONITORING_DIR / "reports"):
        self.report_dir = report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, df: pd.DataFrame) -> dict:
        """Génère le rapport complet."""
        price  = pd.to_numeric(df.get("price_value", pd.Series()), errors="coerce")
        surface = pd.to_numeric(df.get("surface_m2", pd.Series()), errors="coerce")
        ppm2   = (price / surface.replace(0, np.nan)).dropna()

        report = {
            "generated_at": datetime.now().isoformat(),
            "dataset": {
                "n_total":          len(df),
                "n_with_price":     int(price.notna().sum()),
                "n_with_surface":   int(surface.notna().sum()),
                "n_with_gps":       int(df["latitude"].notna().sum()) if "latitude" in df else 0,
                "sources":          df["source"].value_counts().to_dict() if "source" in df else {},
                "cities_top5":      df["city"].value_counts().head(5).to_dict() if "city" in df else {},
                "date_range":       {
                    "min": str(df["scraped_at"].min()) if "scraped_at" in df else None,
                    "max": str(df["scraped_at"].max()) if "scraped_at" in df else None,
                },
            },
            "price_stats": {
                "mean_ppm2":   round(float(ppm2.mean()), 0) if len(ppm2) else None,
                "median_ppm2": round(float(ppm2.median()), 0) if len(ppm2) else None,
                "p10_ppm2":    round(float(ppm2.quantile(0.10)), 0) if len(ppm2) else None,
                "p90_ppm2":    round(float(ppm2.quantile(0.90)), 0) if len(ppm2) else None,
            },
            "ml_scores": {},
            "recommendations": [],
        }

        # Trust scores si disponibles
        if "trust_score" in df.columns:
            report["ml_scores"]["trust"] = {
                "mean":     round(float(df["trust_score"].mean()), 4),
                "n_fiable": int((df["trust_score"] >= 0.75).sum()),
                "n_suspect": int((df["trust_score"] < 0.45).sum()),
            }

        if "is_anomaly" in df.columns:
            report["ml_scores"]["anomaly"] = {
                "n_anomalies": int(df["is_anomaly"].sum()),
                "pct": round(float(df["is_anomaly"].mean() * 100), 1),
            }

        # Recommandations
        n = len(df)
        if n < 5000:
            report["recommendations"].append("⚠️  Volume faible — lancer les scrapers")
        gps_rate = report["dataset"]["n_with_gps"] / max(n, 1)
        if gps_rate < 0.60:
            report["recommendations"].append(f"⚠️  GPS rate={gps_rate:.0%} — améliorer le géocodage")

        # Sauvegarde
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = self.report_dir / f"pipeline_report_{ts}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        report["report_path"] = str(out)
        return report

    def print_report(self, report: dict):
        print("\n" + "="*60)
        print("  PIPELINE REPORT — Estate Mind")
        print("="*60)
        d = report["dataset"]
        print(f"  Total annonces     : {d['n_total']:,}")
        print(f"  Avec prix          : {d['n_with_price']:,}")
        print(f"  Avec GPS           : {d['n_with_gps']:,}")
        print(f"  Sources            : {d['sources']}")
        p = report["price_stats"]
        print(f"\n  Prix médian/m²     : {p['median_ppm2']} TND")
        print(f"  Prix moyen/m²      : {p['mean_ppm2']} TND")
        if report["recommendations"]:
            print(f"\n  Recommandations :")
            for r in report["recommendations"]:
                print(f"    {r}")
        print("="*60)


# ═══════════════════════════════════════════════════════════════════════════════
# Main standalone
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/annonces_combined.csv"
    out_dir  = sys.argv[2] if len(sys.argv) > 2 else "results"
    os.makedirs(out_dir, exist_ok=True)

    print("\n📡 Monitoring Tools — Estate Mind")

    df = pd.read_csv(csv_path, sep=";", on_bad_lines="skip", encoding="latin1")
    for col in ["price_value", "surface_m2", "latitude"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["price_per_m2"] = df["price_value"] / df["surface_m2"].replace(0, np.nan)
    print(f"   {len(df):,} annonces chargées")

    # 1. Source Health
    print("\n[1/3] Source Health Monitor")
    monitor = SourceHealthMonitor()
    health  = monitor.check(df)
    print(f"   Score global : {health['global_health_score']}")
    for src, info in health["sources"].items():
        status = "✅" if info["status"] == "ok" else "⚠️"
        print(f"   {status} {src:<12}: {info['n_annonces']} annonces, "
              f"GPS={info['gps_rate']:.0%}")

    # 2. Drift Detection
    print("\n[2/3] Drift Detector")
    drift = DriftDetector()
    if not drift.reference:
        drift.save_reference(df)
    result = drift.check_drift(df)
    print(f"   Drift détecté : {result['drift_detected']}")
    print(f"   {result['recommendation']}")

    # 3. Pipeline Report
    print("\n[3/3] Pipeline Reporter")
    reporter = PipelineReporter()
    report   = reporter.generate(df)
    reporter.print_report(report)

    # Sauvegarde résumé
    out_file = f"{out_dir}/monitoring_summary.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp":    datetime.now().isoformat(),
            "health":       health,
            "drift":        result,
            "pipeline":     {k: v for k, v in report.items() if k != "report_path"},
        }, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Résumé monitoring → {out_file}")
