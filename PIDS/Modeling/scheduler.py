"""
Estate Mind — scheduler.py (VERSION 2 — CORRIGÉE)
===================================================
Corrections vs v1 :
  ✅ Remax : détecte remax_initial_*.csv ET remax_update_*.csv
  ✅ Tecnocasa : verrou threading pour éviter les runs en double
  ✅ Supabase : force float64 avant upsert (fix decimal.Decimal)
  ✅ Runs trop longs (>5min) : le scheduler skip le run suivant proprement

Lancement :
    cd Modeling/
    python scheduler.py
"""

from __future__ import annotations
import json
import queue
import sys
import threading
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

# ── Verrou pour empêcher les doubles runs ─────────────────────────────────────
_run_lock = threading.Lock()

# ── Queue SSE partagée avec main_api.py ──────────────────────────────────────
notification_queue: queue.Queue = queue.Queue()

_last_run_stats: dict = {
    "last_run":       None,
    "new_listings":   0,
    "total_listings": 6877,
    "sources":        {},
    "status":         "idle",
}


def _notify(message: str, data: dict = None):
    payload = {
        "type":      "new_data",
        "message":   message,
        "data":      data or {},
        "timestamp": datetime.utcnow().isoformat(),
    }
    notification_queue.put(json.dumps(payload, ensure_ascii=False))
    logger.info(f"[Notif] {message}")


def get_last_run_stats() -> dict:
    return _last_run_stats.copy()


# ── Lecture CSV robuste ───────────────────────────────────────────────────────

def _read_csv_safe(path) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    for enc in ["utf-8", "utf-8-sig", "latin1"]:
        try:
            df = pd.read_csv(p, encoding=enc, on_bad_lines="skip", low_memory=False)
            df = df[[c for c in df.columns if not str(c).startswith("Unnamed")]]
            if len(df) > 0:
                return df
        except Exception:
            continue
    return pd.DataFrame()


def _latest_csv(pattern: str) -> Path | None:
    """Retourne le CSV le plus récent correspondant au pattern."""
    files = list(Path(ROOT / "data" / "raw").glob(pattern))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


# ── Scraper 1 — Tayara ────────────────────────────────────────────────────────

def _scrape_tayara(max_pages: int = 3) -> pd.DataFrame:
    try:
        from scrapers.tayara_scraper_optimized import (
            TayaraScraper, TayaraConfig, load_state, save_state, now_stamp
        )
        cfg = TayaraConfig(
            max_pages=max_pages,
            sleep_sec=0.2,
            scrape_detail=False,
            workers=4,
            stop_after_seen_streak=30,
            stop_after_old_pages=2,
            detail_sleep_sec=0.1,
            extra_params={},
        )
        scraper      = TayaraScraper(cfg)
        state        = load_state(cfg)
        rows_new, new_state = scraper.run_update(state)

        if not rows_new:
            logger.info("[Tayara] Aucune nouvelle annonce")
            return pd.DataFrame()

        save_state(cfg, new_state)
        df = pd.DataFrame(rows_new)
        df["source"] = "tayara"
        logger.info(f"[Tayara] {len(df)} nouvelles annonces")
        return df
    except Exception as e:
        logger.error(f"[Tayara] Erreur : {e}")
        return pd.DataFrame()


# ── Scraper 2 — Mubawab ──────────────────────────────────────────────────────

def _scrape_mubawab(max_pages: int = 3) -> pd.DataFrame:
    try:
        from scrapers.mubawab_scraper import run_update
        csv_path = run_update(max_pages=max_pages)
        if csv_path is None:
            logger.info("[Mubawab] Aucune nouvelle annonce")
            return pd.DataFrame()
        df = _read_csv_safe(csv_path)
        if df.empty:
            return pd.DataFrame()
        df["source"] = "mubawab"
        logger.info(f"[Mubawab] {len(df)} nouvelles annonces")
        return df
    except Exception as e:
        logger.error(f"[Mubawab] Erreur : {e}")
        return pd.DataFrame()


# ── Scraper 3 — Remax (CORRIGÉ) ──────────────────────────────────────────────

def _scrape_remax(max_pages: int = 3) -> pd.DataFrame:
    """
    Fix : cherche remax_initial_*.csv ET remax_update_*.csv
    (la première fois il y a pas de state → run_update fait un initial)
    """
    try:
        from scrapers.remax_search_api import run_update, RAW_DIR

        raw_dir = Path(RAW_DIR)
        # Snapshot avant
        before = set(raw_dir.glob("remax_*.csv")) if raw_dir.exists() else set()

        run_update(max_pages=max_pages, sleep_s=0.2, seen_streak_stop=3)

        # Snapshot après — cherche TOUT nouveau fichier remax
        after     = set(raw_dir.glob("remax_*.csv")) if raw_dir.exists() else set()
        new_files = after - before

        if not new_files:
            logger.info("[Remax] Aucune nouvelle annonce")
            return pd.DataFrame()

        csv_path = max(new_files, key=lambda p: p.stat().st_mtime)
        df = _read_csv_safe(csv_path)
        if df.empty:
            return pd.DataFrame()

        df["source"] = "remax"
        # Normaliser colonnes Remax
        col_map = {
            "ListingPrice": "price_value",
            "TotalArea":    "surface_m2",
            "LivingArea":   "surface_m2",
            "City":         "city",
            "NumberOfBedrooms":  "bedrooms",
            "NumberOfBathrooms": "bathrooms",
            "Latitude":     "latitude",
            "Longitude":    "longitude",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        logger.info(f"[Remax] {len(df)} nouvelles annonces → {csv_path.name}")
        return df

    except Exception as e:
        logger.error(f"[Remax] Erreur : {e}")
        return pd.DataFrame()


# ── Scraper 4 — Tecnocasa (avec verrou anti-doublon) ─────────────────────────

_tecno_lock = threading.Lock()

def _scrape_tecnocasa(max_pages: int = 3) -> pd.DataFrame:
    """Tecnocasa avec verrou pour éviter les exécutions parallèles."""
    if not _tecno_lock.acquire(blocking=False):
        logger.warning("[Tecnocasa] Déjà en cours → skip")
        return pd.DataFrame()
    try:
        from scrapers.tecnocasa_scraper import scrape_tecnocasa, RAW_DIR

        raw_dir = Path(RAW_DIR)
        before  = set(raw_dir.glob("tecnocasa_update_*.csv")) if raw_dir.exists() else set()

        csv_path = scrape_tecnocasa(mode="update", max_pages=max_pages)

        after     = set(raw_dir.glob("tecnocasa_update_*.csv")) if raw_dir.exists() else set()
        new_files = after - before

        # Utiliser le path retourné en priorité
        if csv_path is not None:
            target = Path(csv_path)
        elif new_files:
            target = max(new_files, key=lambda p: p.stat().st_mtime)
        else:
            logger.info("[Tecnocasa] Aucune nouvelle annonce")
            return pd.DataFrame()

        df = _read_csv_safe(target)
        if df.empty:
            return pd.DataFrame()

        df["source"] = "tecnocasa"
        logger.info(f"[Tecnocasa] {len(df)} nouvelles annonces")
        return df
    except Exception as e:
        logger.error(f"[Tecnocasa] Erreur : {e}")
        return pd.DataFrame()
    finally:
        _tecno_lock.release()


# ── Normalisation + ML + Supabase ─────────────────────────────────────────────

def _process_and_push(df: pd.DataFrame) -> int:
    # Normalisation colonnes
    col_map = {
        "price":    "price_value", "Price": "price_value",
        "surface":  "surface_m2",  "Surface": "surface_m2",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # ✅ Fix decimal.Decimal → forcer float64 sur toutes les colonnes numériques
    for col in ["price_value", "surface_m2", "latitude", "longitude",
                "bedrooms", "bathrooms", "price_per_m2"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    if "price_per_m2" not in df.columns and "price_value" in df.columns and "surface_m2" in df.columns:
        df["price_per_m2"] = (df["price_value"] / df["surface_m2"].replace(0, np.nan)).astype("float64")

    # Nettoyage
    try:
        from tools.cleaning_tools import run_full_cleaning
        df = run_full_cleaning(df)
    except Exception as e:
        logger.warning(f"[Nettoyage] Partiel : {e}")

    if df.empty:
        return 0

    # Re-forcer float64 après nettoyage (cleaning_tools peut changer les types)
    for col in ["price_value", "surface_m2", "latitude", "longitude",
                "bedrooms", "bathrooms", "price_per_m2"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    # Trust M1
    try:
        from tools.ml_risk_tools import predict_trust_batch
        df = predict_trust_batch(df)
    except Exception:
        try:
            from tools.risk_tools import run_trust_scoring
            df = run_trust_scoring(df)
        except Exception:
            pass

    # Anomaly M2
    try:
        m2p = ROOT / "models" / "saved" / "m2_isolation_forest.joblib"
        scp = ROOT / "models" / "saved" / "m2_scaler.joblib"
        if m2p.exists() and "price_value" in df.columns:
            from joblib import load
            m2 = load(m2p); scaler = load(scp)
            FEAT = ["price_value", "surface_m2", "price_per_m2", "bedrooms"]
            for c in FEAT:
                if c not in df.columns: df[c] = np.nan
            X  = df[FEAT].fillna(df[FEAT].median()).astype("float64")
            Xs = scaler.transform(X)
            df["is_anomaly"]    = (m2.predict(Xs) == -1)
            df["anomaly_score"] = np.clip(-m2.decision_function(Xs)/0.5, 0, 1).round(4)
    except Exception as e:
        logger.warning(f"[M2] {e}")

    # Sentiment
    try:
        from tools.sentiment_analyzer import SentimentAnalyzer
        df = SentimentAnalyzer(use_llm=False).analyze_batch(df, use_llm=False)
    except Exception:
        pass

    # ── Fix timestamps : unix int → ISO datetime ────────────────────────────
    ts_cols = ["publication_date","scraped_at","first_seen_at","last_updated",
               "FirstUpdatedToWeb","LastUpdatedOnWeb","OrigListingDate","ExpiryDate"]
    for col in ts_cols:
        if col not in df.columns:
            continue
        if df[col].dtype == object:
            continue  # déjà string
        try:
            df[col] = pd.to_datetime(df[col], unit='s', errors='coerce') \
                        .dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
        except Exception:
            df[col] = None

    # ✅ Fix Supabase : forcer float64 une dernière fois avant upsert
    for col in df.select_dtypes(include=["object"]).columns:
        try:
            converted = pd.to_numeric(df[col], errors="ignore")
            if converted.dtype != object:
                df[col] = converted.astype("float64")
        except Exception:
            pass

    # Push Supabase
    n_pushed = 0
    try:
        from db.supabase_manager import get_db
        db = get_db()
        if hasattr(db, "upsert_listings"):
            stats    = db.upsert_listings(df, pipeline_version="scheduler_v2")
            n_pushed = stats.get("inserted", 0) + stats.get("updated", 0)
        elif hasattr(db, "insert_annonces"):
            n_pushed = db.insert_annonces(df)
        logger.info(f"[Supabase] {n_pushed} annonces pushées")
    except Exception as e:
        logger.error(f"[Supabase] Push échoué : {e}")
    return n_pushed


# ── Pipeline principal ────────────────────────────────────────────────────────

def run_update_pipeline():
    global _last_run_stats

    # Anti-doublon global
    if not _run_lock.acquire(blocking=False):
        logger.warning("[Scheduler] Run en cours → skip")
        return

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    t0     = time.time()

    logger.info(f"\n{'='*52}")
    logger.info(f"[Scheduler] 🚀 Run UPDATE — {run_id}")
    logger.info(f"{'='*52}")

    _last_run_stats["status"]   = "running"
    _last_run_stats["last_run"] = datetime.utcnow().isoformat()

    try:
        scrapers = [
            ("tayara",    _scrape_tayara),
            ("mubawab",   _scrape_mubawab),
            ("remax",     _scrape_remax),
            ("tecnocasa", _scrape_tecnocasa),
        ]

        all_dfs = []
        sources = {}

        for name, fn in scrapers:
            df_new = fn(max_pages=3)
            if df_new is not None and not df_new.empty:
                all_dfs.append(df_new)
                sources[name] = len(df_new)

        if not all_dfs:
            logger.info("[Scheduler] Aucune nouvelle annonce")
            _last_run_stats.update({"status":"idle","new_listings":0,"sources":sources})
            return

        df_all   = pd.concat(all_dfs, ignore_index=True)
        n_pushed = _process_and_push(df_all)
        elapsed  = round(time.time() - t0, 1)

        n_fiable = 0
        for col in ["trust_label","trust_level"]:
            if col in df_all.columns:
                n_fiable = int((df_all[col] == "Fiable").sum())
                break

        _last_run_stats.update({
            "last_run":       datetime.utcnow().isoformat(),
            "new_listings":   len(df_all),
            "total_listings": _last_run_stats.get("total_listings",6877) + n_pushed,
            "sources":        sources,
            "n_fiable":       n_fiable,
            "n_pushed":       n_pushed,
            "duration_s":     elapsed,
            "status":         "idle",
        })

        if n_pushed > 0:
            _notify(
                f"🏠 {n_pushed} nouvelles annonces ajoutées au marché !",
                {"n_new":n_pushed,"n_fiable":n_fiable,
                 "sources":sources,"duration_s":elapsed,"run_id":run_id}
            )
        logger.info(f"[Scheduler] ✅ {elapsed}s — {len(df_all)} scrappées · {n_pushed} pushées")

    finally:
        _last_run_stats["status"] = "idle"
        _run_lock.release()


# ── Lancement ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("🕐 Estate Mind Scheduler v2 — UPDATE toutes les 5 minutes")
    logger.info(f"   Démarrage : {datetime.now().strftime('%H:%M:%S')}")
    logger.info("   Ctrl+C pour arrêter\n")

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        scheduler = BackgroundScheduler(timezone="Africa/Tunis")
        scheduler.add_job(
            func=run_update_pipeline,
            trigger=IntervalTrigger(minutes=5),
            id="estate_mind_update",
            replace_existing=True,
            max_instances=1,    # APScheduler skip si déjà en cours
        )
        scheduler.start()
        logger.info("✅ Scheduler démarré — toutes les 5 minutes")
        logger.info("🚀 Premier run immédiat...\n")
        run_update_pipeline()

        while True:
            jobs = scheduler.get_jobs()
            if jobs:
                logger.info(f"⏳ Prochain run : {jobs[0].next_run_time.strftime('%H:%M:%S')}")
            time.sleep(60)

    except ImportError:
        logger.warning("APScheduler manquant → pip install apscheduler")
        while True:
            run_update_pipeline()
            logger.info("⏳ Prochain run dans 5 minutes...")
            time.sleep(300)
    except KeyboardInterrupt:
        logger.info("\n🛑 Scheduler arrêté")
