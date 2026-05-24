"""
Estate Mind — Injection directe des CSV dans Supabase
══════════════════════════════════════════════════════
Ce script court-circuite complètement le scraping.
Il prend tes CSV déjà collectés dans data/raw/,
les nettoie, calcule les trust scores, et les injecte
dans Supabase.

AVANTAGES vs relancer le pipeline complet :
  ✅ Pas de scraping → pas de timeout réseau
  ✅ Pas de dépendance à bs4 / API externes
  ✅ 10x plus rapide
  ✅ Fonctionne avec les données que tu as déjà
  ✅ L'API OpenAI est optionnelle (--no-nlp pour skipper)

USAGE :
    # Injection rapide SANS enrichissement NLP (2-3 min)
    python inject_csv.py --no-nlp

    # Injection complète AVEC enrichissement NLP (+ lente, utilise OpenAI)
    python inject_csv.py

    # Spécifier un CSV particulier
    python inject_csv.py --csv data/raw/annonces_combined.csv

    # Voir ce qui serait injecté sans le faire
    python inject_csv.py --dry-run

FLOW :
    data/raw/*.csv → combine → nettoie → trust score → Supabase
"""
import sys
import argparse
import json
import uuid
from datetime import datetime
from pathlib import Path

# ── Setup du path ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from loguru import logger

# ── Config ───────────────────────────────────────────────────────────────────
RAW_DIR   = BASE_DIR / "data" / "raw"
PROC_DIR  = BASE_DIR / "data" / "processed"
CLEAN_CSV = PROC_DIR / "listings_clean.csv"


# ══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 1 : Chargement et fusion des CSV
# ══════════════════════════════════════════════════════════════════════════════

def load_all_raw_csvs(specific_csv: str = None) -> pd.DataFrame:
    """
    Charge et fusionne tous les CSV bruts disponibles.
    Si specific_csv est fourni, ne charge que celui-là.
    
    Gère automatiquement les deux formats :
      - Séparateur virgule (listings_clean.csv, mubawab, tecnocasa)
      - Séparateur point-virgule (annonces_combined.csv tayara)
    """
    if specific_csv:
        paths = [Path(specific_csv)]
        if not paths[0].exists():
            logger.error(f"Fichier introuvable : {specific_csv}")
            sys.exit(1)
    else:
        # Tous les CSV dans data/raw/
        paths = sorted(RAW_DIR.glob("*.csv"))
        if not paths:
            logger.error(f"Aucun CSV trouvé dans {RAW_DIR}")
            logger.info("→ Placez vos fichiers CSV dans data/raw/ et relancez")
            sys.exit(1)

    logger.info(f"[Injection] {len(paths)} fichier(s) CSV trouvé(s) :")
    for p in paths:
        logger.info(f"  → {p.name} ({p.stat().st_size // 1024} Ko)")

    dfs = []
    for path in paths:
        for sep in [",", ";", "\t"]:
            try:
                df = pd.read_csv(
                    path, sep=sep, on_bad_lines="skip",
                    encoding="utf-8", encoding_errors="replace",
                    low_memory=False,
                )
                if len(df.columns) >= 3 and len(df) > 0:
                    df["_source_file"] = path.name
                    dfs.append(df)
                    logger.info(f"  ✅ {path.name} → {len(df)} lignes ({len(df.columns)} colonnes)")
                    break
            except Exception as e:
                continue
        else:
            logger.warning(f"  ⚠️  Impossible de lire {path.name}")

    if not dfs:
        logger.error("Aucun CSV lisible trouvé.")
        sys.exit(1)

    df_all = pd.concat(dfs, ignore_index=True)
    logger.info(f"[Injection] Total brut : {len(df_all)} lignes")
    return df_all


# ══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 2 : Harmonisation des colonnes
# ══════════════════════════════════════════════════════════════════════════════

def harmonize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Harmonise les colonnes entre les différents formats CSV.
    
    Tayara utilise : price_value, surface_m2, region
    Mubawab utilise : price, surface, governorate
    Tecnocasa utilise : price, surface, region
    
    On normalise tout vers le schéma commun d'Estate Mind.
    """
    df = df.copy()

    # Prix : price_value → price
    if "price" not in df.columns:
        for alt in ["price_value", "Prix", "prix", "PRICE"]:
            if alt in df.columns:
                df["price"] = pd.to_numeric(df[alt], errors="coerce")
                break
    else:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")

    # Surface : surface_m2 → surface
    if "surface" not in df.columns:
        for alt in ["surface_m2", "Surface", "area", "SURFACE"]:
            if alt in df.columns:
                df["surface"] = pd.to_numeric(df[alt], errors="coerce")
                break
    else:
        df["surface"] = pd.to_numeric(df["surface"], errors="coerce")

    # Gouvernorat : region → governorate
    if "governorate" not in df.columns:
        for alt in ["region", "Region", "gouvernorat", "Governorate"]:
            if alt in df.columns:
                df["governorate"] = df[alt].astype(str)
                break

    # Source : déterminée depuis le nom du fichier si absente
    if "source" not in df.columns:
        if "_source_file" in df.columns:
            def _guess_source(fname):
                f = str(fname).lower()
                if "tayara" in f or "annonces_combined" in f: return "tayara"
                if "mubawab" in f: return "mubawab"
                if "tecnocasa" in f: return "tecnocasa"
                if "remax" in f: return "remax"
                return "csv"
            df["source"] = df["_source_file"].apply(_guess_source)
        else:
            df["source"] = "csv"

    # URL : obligatoire pour la déduplication
    if "url" not in df.columns:
        for alt in ["URL", "link", "Link", "lien"]:
            if alt in df.columns:
                df["url"] = df[alt].astype(str)
                break
        else:
            # Génère une URL unique si absente
            df["url"] = (
                "estate-mind://legacy/" +
                df["source"].fillna("unknown") + "/" +
                df.index.astype(str)
            )

    # Titre
    if "title" not in df.columns:
        for alt in ["Title", "titre", "Titre", "name"]:
            if alt in df.columns:
                df["title"] = df[alt].astype(str)
                break
        else:
            df["title"] = ""

    # Ville
    if "city" not in df.columns:
        for alt in ["City", "ville", "Ville", "location"]:
            if alt in df.columns:
                df["city"] = df[alt].astype(str)
                break

    # Property type
    if "property_type" not in df.columns:
        for alt in ["type", "Type", "property", "category"]:
            if alt in df.columns:
                df["property_type"] = df[alt].astype(str)
                break
        else:
            df["property_type"] = "inconnu"

    # Calcul prix/m²
    if "price_per_m2" not in df.columns:
        mask = (df["price"].notna()) & (df["surface"].notna()) & (df["surface"] > 0)
        df["price_per_m2"] = None
        df.loc[mask, "price_per_m2"] = (
            df.loc[mask, "price"] / df.loc[mask, "surface"]
        ).round(2)

    # Nettoie les colonnes temporaires
    df = df.drop(columns=["_source_file"], errors="ignore")

    logger.info(f"[Injection] Colonnes harmonisées. Prix disponibles : "
                f"{df['price'].notna().sum()}/{len(df)}")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 3 : Nettoyage et filtrages de base
# ══════════════════════════════════════════════════════════════════════════════

def basic_clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nettoyage de base sans NLP — rapide, ne nécessite pas OpenAI.
    
    - Supprime les lignes sans URL ni titre
    - Supprime les doublons sur URL
    - Filtre les prix aberrants (< 1 000 TND ou > 10 000 000 TND)
    - Filtre les surfaces aberrantes (< 5 m² ou > 5000 m²)
    """
    n0 = len(df)

    # Supprime les lignes sans URL (impossible à dédupliquer)
    df = df[df["url"].notna() & (df["url"].str.strip() != "")].copy()

    # Déduplication sur URL (garde la première occurrence)
    df = df.drop_duplicates(subset=["url"], keep="first")

    # Filtre prix aberrants (seulement si prix disponible)
    mask_price = df["price"].notna()
    valid_price = (df["price"] >= 1_000) & (df["price"] <= 10_000_000)
    df = df[~mask_price | valid_price].copy()

    # Filtre surfaces aberrantes
    mask_surf = df["surface"].notna()
    valid_surf = (df["surface"] >= 5) & (df["surface"] <= 5_000)
    df = df[~mask_surf | valid_surf].copy()

    logger.info(f"[Injection] Nettoyage : {n0} → {len(df)} lignes "
                f"({n0 - len(df)} supprimées)")
    return df.reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 4 : Trust Scoring
# ══════════════════════════════════════════════════════════════════════════════

def compute_trust_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule les trust scores pour toutes les annonces.
    Utilise run_trust_scoring si disponible, sinon calcul simplifié.
    """
    try:
        from tools.risk_tools import run_trust_scoring
        df = run_trust_scoring(df)
        logger.info(f"[Injection] Trust scores calculés — "
                    f"moyenne : {df['trust_score'].mean():.3f}")
        return df
    except Exception as e:
        logger.warning(f"[Injection] run_trust_scoring indisponible ({e}) "
                       f"→ calcul simplifié")

    # Calcul simplifié si risk_tools non disponible
    scores = []
    for _, row in df.iterrows():
        score = 0.5  # base

        # Prix disponible → +0.1
        if pd.notna(row.get("price")) and row["price"] > 0:
            score += 0.1

        # Surface disponible → +0.1
        if pd.notna(row.get("surface")) and row["surface"] > 0:
            score += 0.1

        # Source fiable → bonus
        source_bonus = {
            "remax": 0.2, "tecnocasa": 0.15,
            "mubawab": 0.05, "tayara": 0.0, "csv": 0.0,
        }
        score += source_bonus.get(str(row.get("source", "")).lower(), 0)

        # Prix/m² cohérent (entre 200 et 10 000 TND/m²)
        ppm2 = row.get("price_per_m2")
        if pd.notna(ppm2) and 200 <= ppm2 <= 10_000:
            score += 0.1

        scores.append(min(score, 1.0))

    df["trust_score"] = scores
    df["trust_level"] = df["trust_score"].apply(
        lambda s: "Fiable" if s >= 0.75 else ("Moyen" if s >= 0.5 else "Suspect")
    )
    df["legal_risk_score"] = 0.15
    df["legal_risk_level"] = "Faible"

    logger.info(f"[Injection] Trust scores simplifiés — "
                f"moyenne : {df['trust_score'].mean():.3f}")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 5 : Enrichissement NLP (optionnel)
# ══════════════════════════════════════════════════════════════════════════════

def nlp_enrich(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrichissement NLP via OpenAI — optionnel, peut être skippé avec --no-nlp.
    Extrait les champs manquants depuis les descriptions.
    """
    try:
        from tools.nlp_cleaner import run_nlp_enrichment
        df = run_nlp_enrichment(df)
        logger.info("[Injection] Enrichissement NLP terminé")
        return df
    except ImportError:
        logger.warning("[Injection] nlp_cleaner non disponible — skip NLP")
        return df
    except Exception as e:
        logger.warning(f"[Injection] NLP échoué ({e}) — données inchangées")
        return df


# ══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 6 : Injection dans Supabase
# ══════════════════════════════════════════════════════════════════════════════

def inject_to_supabase(df: pd.DataFrame, pipeline_version: str) -> dict:
    """
    Injecte le DataFrame dans Supabase via le SupabaseManager.
    Retourne les stats d'upsert.
    """
    try:
        from db.supabase_manager import get_db
        db = get_db()

        if not db.is_available:
            logger.warning("[Injection] Supabase non disponible → CSV uniquement")
            return inject_to_csv_only(df)

        db.ensure_tables()
        stats = db.upsert_listings(df, pipeline_version=pipeline_version)
        return stats

    except ImportError:
        logger.warning("[Injection] supabase_manager non disponible → essai postgres_manager")
        try:
            from db.postgres_manager import PostgresManager
            pg = PostgresManager()
            pg.ensure_tables()
            stats = pg.upsert_listings(df, pipeline_version=pipeline_version)
            return stats
        except Exception as e:
            logger.error(f"[Injection] postgres_manager aussi indisponible : {e}")
            return inject_to_csv_only(df)


def inject_to_csv_only(df: pd.DataFrame) -> dict:
    """Sauvegarde locale uniquement si Supabase indisponible."""
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN_CSV, index=False)
    logger.info(f"[Injection] Sauvegardé localement : {CLEAN_CSV}")
    return {"inserted": len(df), "updated": 0, "skipped": 0, "mode": "csv_only"}


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Injecte les CSV existants dans Supabase sans scraping"
    )
    parser.add_argument(
        "--csv",
        help="Chemin vers un CSV spécifique (défaut: tous les CSV de data/raw/)",
        default=None,
    )
    parser.add_argument(
        "--no-nlp",
        action="store_true",
        help="Désactive l'enrichissement NLP (plus rapide, pas besoin d'OpenAI)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyse les CSV sans injecter dans Supabase",
    )
    parser.add_argument(
        "--version",
        default="inject_v1",
        help="Version du pipeline à logger dans Supabase",
    )
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("  ESTATE MIND — Injection CSV → Supabase")
    print("═" * 60)
    print(f"  Mode NLP    : {'❌ Désactivé (--no-nlp)' if args.no_nlp else '✅ Activé'}")
    print(f"  Dry run     : {'✅ Oui (aucune écriture)' if args.dry_run else '❌ Non'}")
    print(f"  Source      : {args.csv or 'tous les CSV de data/raw/'}")
    print("═" * 60 + "\n")

    t0 = datetime.utcnow()

    # ── 1. Chargement ─────────────────────────────────────────────────────────
    print("📂 ÉTAPE 1/5 — Chargement des CSV...")
    df = load_all_raw_csvs(args.csv)

    # ── 2. Harmonisation ──────────────────────────────────────────────────────
    print("\n🔧 ÉTAPE 2/5 — Harmonisation des colonnes...")
    df = harmonize_columns(df)

    # ── 3. Nettoyage complet via run_full_cleaning ───────────────────────────
    print("\n🧹 ÉTAPE 3/5 — Nettoyage, normalisation et déduplication...")
    try:
        from tools.cleaning_tools import run_full_cleaning
        df = run_full_cleaning(df)
        print(f"  ✅ Pipeline nettoyage OK — {len(df)} lignes, {len(df.columns)} colonnes")
    except Exception as e:
        logger.warning(f"run_full_cleaning indisponible ({e}) → nettoyage basique")
        df = basic_clean(df)

    if args.dry_run:
        print("\n" + "═" * 60)
        print("  DRY RUN — Résumé (aucune écriture effectuée)")
        print("═" * 60)
        print(f"  Lignes totales     : {len(df)}")
        for col in ['price','surface','rooms','property_type','city']:
            if col in df.columns:
                nn = df[col].notna().sum()
                print(f"  {col:20s}: {nn}/{len(df)} ({nn/len(df)*100:.0f}%)")
        print(f"  Sources présentes  : {df['source'].value_counts().to_dict() if 'source' in df.columns else 'N/A'}")
        print("\n  → Relancez sans --dry-run pour injecter dans Supabase")
        return

    # ── 4. Trust scoring ──────────────────────────────────────────────────────
    print("\n🛡️  ÉTAPE 4/5 — Calcul des Trust Scores...")
    df = compute_trust_scores(df)

    # ── 5. NLP (optionnel) ────────────────────────────────────────────────────
    if not args.no_nlp:
        print("\n🤖 ÉTAPE 4b — Enrichissement NLP (peut prendre du temps)...")
        print("   → Utilisez --no-nlp pour sauter cette étape")
        df = nlp_enrich(df)
    else:
        print("\n⏭️  ÉTAPE 4b — NLP ignoré (--no-nlp)")

    # ── 6. Sauvegarde CSV locale (toujours) ───────────────────────────────────
    print("\n💾 Sauvegarde CSV locale (listings_clean.csv)...")
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN_CSV, index=False)
    logger.info(f"CSV sauvegardé : {CLEAN_CSV} ({len(df)} lignes)")

    # ── 7. Injection Supabase ─────────────────────────────────────────────────
    print("\n🗃️  ÉTAPE 5/5 — Injection dans Supabase...")
    stats = inject_to_supabase(df, pipeline_version=args.version)

    # ── Résumé final ──────────────────────────────────────────────────────────
    elapsed = (datetime.utcnow() - t0).total_seconds()
    print("\n" + "═" * 60)
    print("  ✅ INJECTION TERMINÉE")
    print("═" * 60)
    print(f"  Durée            : {elapsed:.1f}s")
    print(f"  Lignes traitées  : {len(df)}")
    print(f"  Insérées         : {stats.get('inserted', '?')}")
    print(f"  Mises à jour     : {stats.get('updated', '?')}")
    print(f"  Ignorées         : {stats.get('skipped', '?')}")
    print(f"  Mode             : {stats.get('mode', '?')}")
    print(f"  Trust moyen      : {df['trust_score'].mean():.3f}")
    print(f"  Suspectes (<0.5) : {(df['trust_score'] < 0.5).sum()}")
    print("\n  → Vérifiez dans Supabase → Table Editor → listings")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
