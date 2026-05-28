"""
Estate Mind — inject_initial.py
=================================
Lance le scraping INITIAL pour Remax ET Tecnocasa,
nettoie les données, et les pousse dans Supabase.

Utilisation :
    cd Modeling/
    python inject_initial.py                    # Remax + Tecnocasa
    python inject_initial.py --source remax     # Remax seulement
    python inject_initial.py --source tecnocasa # Tecnocasa seulement
    python inject_initial.py --max-pages 10     # plus de pages
"""

from __future__ import annotations
import argparse
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── Lecture CSV robuste ───────────────────────────────────────────────────────

def read_csv_safe(path) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    p = Path(path)
    if not p.exists():
        logger.error(f"Fichier introuvable : {p}")
        return pd.DataFrame()
    for enc in ["utf-8", "utf-8-sig", "latin1"]:
        try:
            df = pd.read_csv(p, encoding=enc, on_bad_lines="skip", low_memory=False)
            df = df[[c for c in df.columns if not str(c).startswith("Unnamed")]]
            if len(df) > 0:
                logger.info(f"   CSV lu : {p.name} ({len(df)} lignes, enc={enc})")
                return df
        except Exception:
            continue
    return pd.DataFrame()


# ── Scraping Remax INITIAL ────────────────────────────────────────────────────

def scrape_remax_initial(max_pages: int = 50) -> pd.DataFrame:
    logger.info(f"\n{'─'*50}")
    logger.info(f"[Remax] 🚀 Scraping INITIAL — max_pages={max_pages}")
    logger.info(f"{'─'*50}")

    try:
        from scrapers.remax_search_api import run_initial, RAW_DIR
        import glob

        before = set(glob.glob(str(Path(RAW_DIR) / "remax_initial_*.csv")))
        run_initial(max_pages=max_pages, sleep_s=0.3)
        after  = set(glob.glob(str(Path(RAW_DIR) / "remax_initial_*.csv")))

        new_files = after - before
        if not new_files:
            # Prendre le plus récent
            all_files = sorted(glob.glob(str(Path(RAW_DIR) / "remax_*.csv")),
                                key=lambda p: Path(p).stat().st_mtime, reverse=True)
            if all_files:
                new_files = {all_files[0]}
                logger.info(f"[Remax] CSV le plus récent : {Path(all_files[0]).name}")

        if not new_files:
            logger.warning("[Remax] Aucun CSV trouvé après le scraping")
            return pd.DataFrame()

        csv_path = max(new_files, key=lambda p: Path(p).stat().st_mtime)
        df = read_csv_safe(csv_path)
        if df.empty:
            return pd.DataFrame()

        df["source"] = "remax"
        logger.info(f"[Remax] ✅ {len(df)} annonces collectées")
        return df

    except ImportError as e:
        logger.error(f"[Remax] Import échoué : {e}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"[Remax] Erreur : {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


# ── Scraping Tecnocasa INITIAL ────────────────────────────────────────────────

def scrape_tecnocasa_initial(max_pages: int = 50) -> pd.DataFrame:
    logger.info(f"\n{'─'*50}")
    logger.info(f"[Tecnocasa] 🚀 Scraping INITIAL — max_pages={max_pages}")
    logger.info(f"{'─'*50}")

    try:
        from scrapers.tecnocasa_scraper import scrape_tecnocasa, RAW_DIR
        import glob

        before = set(glob.glob(str(Path(RAW_DIR) / "tecnocasa_initial_*.csv")))
        csv_path = scrape_tecnocasa(mode="initial", max_pages=max_pages)
        after  = set(glob.glob(str(Path(RAW_DIR) / "tecnocasa_initial_*.csv")))

        if csv_path is None:
            new_files = after - before
            if new_files:
                csv_path = max(new_files, key=lambda p: Path(p).stat().st_mtime)
            else:
                all_files = sorted(glob.glob(str(Path(RAW_DIR) / "tecnocasa_*.csv")),
                                    key=lambda p: Path(p).stat().st_mtime, reverse=True)
                if all_files:
                    csv_path = all_files[0]

        if csv_path is None:
            logger.warning("[Tecnocasa] Aucun CSV trouvé")
            return pd.DataFrame()

        df = read_csv_safe(csv_path)
        if df.empty:
            return pd.DataFrame()

        df["source"] = "tecnocasa"
        logger.info(f"[Tecnocasa] ✅ {len(df)} annonces collectées")
        return df

    except ImportError as e:
        logger.error(f"[Tecnocasa] Import échoué : {e}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"[Tecnocasa] Erreur : {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


# ── Nettoyage + ML + Supabase ────────────────────────────────────────────────

def process_and_push(df: pd.DataFrame, label: str) -> int:
    logger.info(f"\n[Pipeline] Traitement de {len(df)} annonces ({label})")

    # Normaliser les colonnes
    col_map = {
        "price":        "price_value",
        "Price":        "price_value",
        "ListingPrice": "price_value",
        "surface":      "surface_m2",
        "Surface":      "surface_m2",
        "TotalArea":    "surface_m2",
        "LivingArea":   "surface_m2",
        "NumberOfBedrooms":  "bedrooms",
        "NumberOfBathrooms": "bathrooms",
        "City":         "city",
        "Latitude":     "latitude",
        "Longitude":    "longitude",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # Supprimer les colonnes dupliquées (ex: TotalArea + LivingArea → deux surface_m2)
    df = df.loc[:, ~df.columns.duplicated(keep='first')]

    for col in ["price_value", "surface_m2", "latitude", "longitude",
                "bedrooms", "bathrooms"]:
        if col in df.columns:
            series = df[col]
            # Si duplicata de colonnes → prendre la première
            if isinstance(series, pd.DataFrame):
                series = series.iloc[:, 0]
                df = df.loc[:, ~df.columns.duplicated(keep='first')]
            df[col] = pd.to_numeric(series, errors="coerce")

    # Forcer float (évite les decimal.Decimal Supabase)
    for col in ["price_value", "surface_m2", "latitude", "longitude",
                "bedrooms", "bathrooms"]:
        if col in df.columns:
            df[col] = df[col].astype("float64")

    if "price_per_m2" not in df.columns:
        if "price_value" in df.columns and "surface_m2" in df.columns:
            df["price_per_m2"] = (df["price_value"] / df["surface_m2"].replace(0, np.nan)).astype("float64")

    # Nettoyage
    n_before = len(df)
    try:
        from tools.cleaning_tools import run_full_cleaning
        df = run_full_cleaning(df)
        logger.info(f"[Nettoyage] {n_before} → {len(df)} annonces")
    except Exception as e:
        logger.warning(f"[Nettoyage] Partiel : {e}")
        df = df.dropna(subset=["price_value", "surface_m2"], how="all")
        logger.info(f"[Nettoyage] Fallback : {len(df)} annonces conservées")

    if df.empty:
        logger.warning("[Pipeline] DataFrame vide après nettoyage")
        return 0

    # Trust scoring M1 (fallback heuristique)
    try:
        from tools.ml_risk_tools import predict_trust_batch
        df = predict_trust_batch(df)
        logger.info("[ML] Trust scoring M1 OK")
    except Exception:
        try:
            from tools.risk_tools import run_trust_scoring
            df = run_trust_scoring(df)
            logger.info("[ML] Trust scoring heuristique OK")
        except Exception as e:
            logger.warning(f"[ML] Trust scoring ignoré : {e}")

    # Anomaly M2
    try:
        m2p = ROOT / "models" / "saved" / "m2_isolation_forest.joblib"
        scp = ROOT / "models" / "saved" / "m2_scaler.joblib"
        if m2p.exists() and "price_value" in df.columns:
            from joblib import load
            m2 = load(m2p); scaler = load(scp)
            FEAT = ["price_value", "surface_m2", "price_per_m2", "bedrooms"]
            for c in FEAT:
                if c not in df.columns:
                    df[c] = np.nan
            X  = df[FEAT].fillna(df[FEAT].median()).astype("float64")
            Xs = scaler.transform(X)
            df["is_anomaly"]    = (m2.predict(Xs) == -1)
            df["anomaly_score"] = np.clip(-m2.decision_function(Xs)/0.5, 0, 1).round(4)
            logger.info(f"[ML] Anomaly M2 OK — {df['is_anomaly'].sum()} anomalies")
    except Exception as e:
        logger.warning(f"[ML] M2 ignoré : {e}")

    # Sentiment
    try:
        from tools.sentiment_analyzer import SentimentAnalyzer
        df = SentimentAnalyzer(use_llm=False).analyze_batch(df, use_llm=False)
        logger.info("[Sentiment] OK")
    except Exception as e:
        logger.warning(f"[Sentiment] Ignoré : {e}")

    # ── Fix timestamps : convertir unix int → ISO datetime avant Supabase ──────
    ts_cols = ["publication_date", "scraped_at", "first_seen_at",
               "last_updated", "FirstUpdatedToWeb", "LastUpdatedOnWeb",
               "OrigListingDate", "ExpiryDate", "created_at", "updated_at"]
    for col in ts_cols:
        if col not in df.columns:
            continue
        series = df[col]
        # Si c'est déjà un string datetime → skip
        if series.dtype == object:
            try:
                pd.to_datetime(series.dropna().iloc[0])
                continue  # déjà bon format
            except Exception:
                pass
        # Si c'est un entier (unix timestamp)
        try:
            df[col] = pd.to_datetime(series, unit='s', errors='coerce') \
                        .dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
        except Exception:
            df[col] = None  # si conversion impossible → null

    # Push Supabase
    n_pushed = 0
    try:
        from db.supabase_manager import get_db
        db = get_db()
        if hasattr(db, "upsert_listings"):
            stats    = db.upsert_listings(df, pipeline_version="inject_initial_v1")
            n_pushed = stats.get("inserted", 0) + stats.get("updated", 0)
            logger.info(f"[Supabase] ✅ insérés={stats.get('inserted',0)} "
                        f"mis-à-jour={stats.get('updated',0)} "
                        f"ignorés={stats.get('ignored',0)}")
        elif hasattr(db, "insert_annonces"):
            n_pushed = db.insert_annonces(df)
            logger.info(f"[Supabase] ✅ {n_pushed} annonces insérées")
    except Exception as e:
        logger.error(f"[Supabase] Push échoué : {e}")
        import traceback
        traceback.print_exc()

        # Fallback CSV
        backup = ROOT / "data" / "processed" / f"{label}_inject_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        backup.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(backup, index=False, encoding="utf-8-sig")
        logger.info(f"[Fallback] CSV sauvegardé : {backup}")

    return n_pushed


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Injection initiale Remax + Tecnocasa → Supabase")
    parser.add_argument("--source",    choices=["remax","tecnocasa","all"], default="all")
    parser.add_argument("--max-pages", type=int, default=50,
                        help="Max pages par scraper (défaut: 50 = toutes les annonces)")
    args = parser.parse_args()

    logger.info("\n" + "═"*60)
    logger.info("  Estate Mind — Injection initiale Remax + Tecnocasa")
    logger.info(f"  Source: {args.source} | Max pages: {args.max_pages}")
    logger.info("═"*60)

    t0 = datetime.now()
    total_pushed = 0
    results = {}

    # Remax
    if args.source in ("remax", "all"):
        df_remax = scrape_remax_initial(args.max_pages)
        if not df_remax.empty:
            n = process_and_push(df_remax, "remax")
            total_pushed += n
            results["remax"] = {"scraped": len(df_remax), "pushed": n}
        else:
            results["remax"] = {"scraped": 0, "pushed": 0}

    # Tecnocasa
    if args.source in ("tecnocasa", "all"):
        df_tecno = scrape_tecnocasa_initial(args.max_pages)
        if not df_tecno.empty:
            n = process_and_push(df_tecno, "tecnocasa")
            total_pushed += n
            results["tecnocasa"] = {"scraped": len(df_tecno), "pushed": n}
        else:
            results["tecnocasa"] = {"scraped": 0, "pushed": 0}

    # Résumé
    elapsed = round((datetime.now() - t0).total_seconds(), 1)
    logger.info(f"\n{'═'*60}")
    logger.info(f"  ✅ Injection terminée en {elapsed}s")
    for src, r in results.items():
        logger.info(f"  {src:12} → scrappées={r['scraped']:4}  pushées={r['pushed']:4}")
    logger.info(f"  TOTAL pushé dans Supabase : {total_pushed}")
    logger.info("═"*60)


if __name__ == "__main__":
    main()
