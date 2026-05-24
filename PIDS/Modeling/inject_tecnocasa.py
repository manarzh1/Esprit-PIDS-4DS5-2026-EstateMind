"""
Estate Mind — inject_tecnocasa.py
====================================
Lit TOUS les CSV Tecnocasa dans data/raw/,
normalise les colonnes vers le schéma Supabase,
et pousse dans la base.

Colonnes Tecnocasa → Supabase :
  listing_id       → listing_id
  title            → title
  description      → description
  price_numeric    → price_value   (la version numérique déjà parsée)
  surface_numeric  → surface_m2
  rooms_numeric    → bedrooms
  bathrooms        → bathrooms
  property_type    → property_type
  city_name        → city
  province_name    → region
  detail_url       → url
  lat              → latitude
  lon              → longitude
  scraped_at       → scraped_at
  source           → source (= 'tecnocasa')

Lancement :
    cd Modeling/
    python inject_tecnocasa.py
"""

from __future__ import annotations
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

RAW_DIR = ROOT / "data" / "raw"


# ── Chargement de tous les CSV Tecnocasa ─────────────────────────────────────

def load_all_tecnocasa_csvs() -> pd.DataFrame:
    patterns = [
        "tecnocasa_initial_*.csv",
        "tecnocasa_update_*.csv",
        "tecnocasa_*.csv",
    ]
    files = set()
    for pat in patterns:
        files |= set(RAW_DIR.glob(pat))

    if not files:
        logger.error(f"Aucun CSV Tecnocasa dans {RAW_DIR}")
        logger.error("Lance d'abord : python inject_initial.py --source tecnocasa")
        return pd.DataFrame()

    logger.info(f"[Tecnocasa] {len(files)} CSV trouvés :")
    dfs = []
    for f in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True):
        for enc in ["utf-8", "utf-8-sig", "latin1"]:
            try:
                df = pd.read_csv(f, encoding=enc, on_bad_lines="skip", low_memory=False)
                df = df[[c for c in df.columns if not str(c).startswith("Unnamed")]]
                if len(df) > 0:
                    logger.info(f"   ✅ {f.name} — {len(df)} lignes")
                    dfs.append(df)
                    break
            except Exception:
                continue

    if not dfs:
        return pd.DataFrame()

    df_all = pd.concat(dfs, ignore_index=True)
    logger.info(f"[Tecnocasa] Total brut : {len(df_all)} lignes")
    return df_all


# ── Mapping colonnes Tecnocasa → Supabase ────────────────────────────────────

def normalize_tecnocasa(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("[Tecnocasa] Normalisation des colonnes...")

    df = df.copy()
    df = df.loc[:, ~df.columns.duplicated(keep='first')]

    # ── Mapping explicite ─────────────────────────────────────────────────────
    # Prix : préférer price_numeric (déjà parsé en float) à price (string "200 000 TND")
    if "price_numeric" in df.columns:
        df["price_value"] = pd.to_numeric(df["price_numeric"], errors="coerce")
    elif "price" in df.columns:
        df["price_value"] = pd.to_numeric(df["price"], errors="coerce")

    # Surface
    if "surface_numeric" in df.columns:
        df["surface_m2"] = pd.to_numeric(df["surface_numeric"], errors="coerce")
    elif "surface" in df.columns:
        df["surface_m2"] = pd.to_numeric(df["surface"], errors="coerce")

    # Chambres
    if "rooms_numeric" in df.columns:
        df["bedrooms"] = pd.to_numeric(df["rooms_numeric"], errors="coerce")
    elif "rooms" in df.columns:
        df["bedrooms"] = pd.to_numeric(df["rooms"], errors="coerce")

    # Salles de bain
    if "bathrooms" in df.columns:
        df["bathrooms"] = pd.to_numeric(df["bathrooms"], errors="coerce")

    # Ville
    if "city_name" in df.columns:
        df["city"] = df["city_name"].fillna("")
    elif "city" not in df.columns:
        if "province_name" in df.columns:
            df["city"] = df["province_name"].fillna("")
        else:
            df["city"] = ""

    # Région/gouvernorat
    if "province_name" in df.columns:
        df["region"] = df["province_name"].fillna("")

    # URL
    if "detail_url" in df.columns and "url" not in df.columns:
        df["url"] = df["detail_url"]

    # GPS
    if "lat" in df.columns and "latitude" not in df.columns:
        df["latitude"] = pd.to_numeric(df["lat"], errors="coerce")
    if "lon" in df.columns and "longitude" not in df.columns:
        df["longitude"] = pd.to_numeric(df["lon"], errors="coerce")

    # Listing ID
    if "listing_id" in df.columns:
        df["listing_id"] = df["listing_id"].astype(str)

    # Source
    df["source"] = "tecnocasa"

    # ── Type de bien : normaliser les valeurs Tecnocasa ───────────────────────
    # Tecnocasa utilise "Appartement", "Villa", "Terrain"... → mettre en minuscules
    if "property_type" in df.columns:
        type_map = {
            "appartement":   "appartement",
            "appartements":  "appartement",
            "villa":         "villa",
            "villas":        "villa",
            "terrain":       "terrain",
            "terrains":      "terrain",
            "maison":        "maison",
            "maisons":       "maison",
            "bureau":        "bureau_local",
            "bureaux":       "bureau_local",
            "local":         "bureau_local",
            "immeuble":      "immeuble",
            "immeubles":     "immeuble",
            "studio":        "studio",
            "ferme":         "ferme",
        }
        df["property_type"] = (
            df["property_type"]
            .fillna("autre")
            .str.lower()
            .str.strip()
            .map(lambda x: next((v for k, v in type_map.items() if k in x), x))
        )

    # ── scraped_at : timestamp Tecnocasa peut être entier unix ────────────────
    if "scraped_at" in df.columns:
        col = df["scraped_at"]
        if col.dtype != object:
            df["scraped_at"] = (
                pd.to_datetime(col, unit="s", errors="coerce")
                .dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
            )

    # ── Forcer float64 sur les numériques ─────────────────────────────────────
    for col in ["price_value", "surface_m2", "latitude", "longitude",
                "bedrooms", "bathrooms"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    # ── prix_per_m2 ───────────────────────────────────────────────────────────
    if "price_value" in df.columns and "surface_m2" in df.columns:
        df["price_per_m2"] = (
            df["price_value"] / df["surface_m2"].replace(0, np.nan)
        ).astype("float64")

    # ── Supprimer les colonnes spécifiques Tecnocasa inutiles pour Supabase ───
    cols_to_drop = [
        "price_numeric", "surface_numeric", "rooms_numeric",
        "price", "surface", "rooms",
        "city_name", "province_id", "region_id", "region_name",
        "quarter_name", "detail_url", "lat", "lon",
        "ad_type", "contract", "contract_slug", "property_type_slug",
        "country", "image_main", "is_discounted", "discount",
        "discount_percentage", "exclusive", "top", "virtual_tour",
        "subtitle", "previous_price",
    ]
    df = df.drop(columns=[c for c in cols_to_drop if c in df.columns], errors="ignore")

    logger.info(f"[Tecnocasa] Après normalisation : {len(df)} lignes, {len(df.columns)} colonnes")
    logger.info(f"   Colonnes : {list(df.columns)}")
    return df


# ── Push Supabase ─────────────────────────────────────────────────────────────

def push_to_supabase(df: pd.DataFrame) -> dict:
    # Déduplication interne
    if "url" in df.columns:
        n_before = len(df)
        df = df.drop_duplicates(subset=["url"], keep="first")
        if len(df) < n_before:
            logger.info(f"[Dedup] {n_before - len(df)} doublons URL supprimés → {len(df)} uniques")

    # Filtrer prix aberrants
    if "price_value" in df.columns:
        mask_valid = (
            df["price_value"].notna() &
            df["price_value"].between(1000, 10_000_000)
        )
        n_filtered = (~mask_valid).sum()
        if n_filtered > 0:
            logger.info(f"[Filtre] {n_filtered} annonces prix hors limites supprimées")
            df = df[mask_valid]

    if df.empty:
        logger.warning("[Supabase] DataFrame vide — rien à pusher")
        return {"inserted": 0, "updated": 0, "ignored": 0}

    try:
        from db.supabase_manager import get_db
        db = get_db()
        if hasattr(db, "upsert_listings"):
            stats = db.upsert_listings(df, pipeline_version="inject_tecnocasa_v1")
            logger.info(f"[Supabase] ✅ insérés={stats.get('inserted',0)} "
                        f"mis-à-jour={stats.get('updated',0)} "
                        f"ignorés={stats.get('ignored',0)}")
            return stats
        elif hasattr(db, "insert_annonces"):
            n = db.insert_annonces(df)
            logger.info(f"[Supabase] ✅ {n} annonces insérées")
            return {"inserted": n, "updated": 0, "ignored": 0}
    except Exception as e:
        logger.error(f"[Supabase] Push échoué : {e}")
        import traceback
        traceback.print_exc()

        # Fallback CSV
        backup = ROOT / "data" / "processed" / f"tecnocasa_supabase_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        backup.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(backup, index=False, encoding="utf-8-sig")
        logger.info(f"[Fallback] CSV sauvegardé : {backup}")
        return {"inserted": 0, "updated": 0, "ignored": 0}


# ── ML scoring ────────────────────────────────────────────────────────────────

def score_df(df: pd.DataFrame) -> pd.DataFrame:
    # Trust M1
    try:
        from tools.ml_risk_tools import predict_trust_batch
        df = predict_trust_batch(df)
        logger.info("[ML] Trust scoring OK")
    except Exception:
        try:
            from tools.risk_tools import run_trust_scoring
            df = run_trust_scoring(df)
        except Exception as e:
            logger.warning(f"[ML] Trust ignoré : {e}")

    # Sentiment
    try:
        from tools.sentiment_analyzer import SentimentAnalyzer
        df = SentimentAnalyzer(use_llm=False).analyze_batch(df, use_llm=False)
        logger.info("[Sentiment] OK")
    except Exception as e:
        logger.warning(f"[Sentiment] ignoré : {e}")

    return df


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("\n" + "═"*60)
    logger.info("  Estate Mind — Injection Tecnocasa → Supabase")
    logger.info("═"*60)

    t0 = datetime.now()

    # 1. Charger tous les CSV
    df = load_all_tecnocasa_csvs()
    if df.empty:
        logger.error("Aucune donnée Tecnocasa trouvée. Abort.")
        sys.exit(1)

    # 2. Normaliser
    df = normalize_tecnocasa(df)

    # 3. Scoring ML
    df = score_df(df)

    # 4. Push Supabase
    stats = push_to_supabase(df)

    elapsed = round((datetime.now() - t0).total_seconds(), 1)
    total   = stats.get("inserted", 0) + stats.get("updated", 0)

    logger.info(f"\n{'═'*60}")
    logger.info(f"  ✅ Terminé en {elapsed}s")
    logger.info(f"  Tecnocasa → Supabase : {total} annonces")
    logger.info(f"  (insérées={stats.get('inserted',0)} "
                f"mises-à-jour={stats.get('updated',0)})")
    logger.info("═"*60)
