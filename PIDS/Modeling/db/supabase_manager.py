"""
Estate Mind — Supabase Manager v1.0
════════════════════════════════════
Couche d'accès données vers Supabase (PostgreSQL managé).

Ce fichier REMPLACE l'accès direct aux CSV dans main_api.py.
Il expose les mêmes méthodes que l'ancienne approche CSV,
mais lit et écrit depuis Supabase avec un fallback CSV automatique.

Architecture :
  SupabaseManager          → interface haut niveau
    ├── _get_conn()        → connexion PostgreSQL via psycopg2
    ├── load_listings()    → charge les annonces (remplace pd.read_csv)
    ├── upsert_listings()  → insère/met à jour sans doublons
    ├── get_price_history()→ historique réel pour PriceHistory.tsx
    ├── portfolio_*()      → gestion favoris utilisateurs
    └── subscriptions_*()  → gestion alertes email

Fallback CSV :
  Si Supabase est indisponible (pas de DATABASE_URL, réseau, etc.),
  toutes les méthodes tombent sur le CSV local automatiquement.
  L'app continue de fonctionner — jamais de crash total.

Usage :
    from db.supabase_manager import get_db
    db = get_db()  # singleton thread-safe
    df = db.load_listings()
    stats = db.upsert_listings(df_clean)
"""
from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

import pandas as pd
from loguru import logger

# ──────────────────────────────────────────────────────────────────────────────
# Import conditionnel de psycopg2 — ne plante pas si non installé
# ──────────────────────────────────────────────────────────────────────────────
try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logger.warning("[supabase] psycopg2 non disponible — mode CSV uniquement")


# ──────────────────────────────────────────────────────────────────────────────
# Configuration — lue depuis les variables d'environnement
# ──────────────────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Chemins CSV fallback
_BASE = Path(__file__).resolve().parent.parent
CLEAN_CSV = _BASE / "data" / "processed" / "listings_clean.csv"
RAW_CSV   = _BASE / "data" / "raw"       / "annonces_combined.csv"


# ══════════════════════════════════════════════════════════════════════════════
# CONNEXION
# ══════════════════════════════════════════════════════════════════════════════

@contextmanager
def _get_conn() -> Generator:
    """Context manager PostgreSQL — connexion + auto-commit/rollback/close."""
    if not PSYCOPG2_AVAILABLE or not DATABASE_URL:
        raise RuntimeError("psycopg2 non disponible ou DATABASE_URL manquant")
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=8)
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"[supabase] Erreur connexion : {e}")
        raise
    finally:
        if conn:
            conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# MANAGER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class SupabaseManager:
    """
    Interface principale pour les données Estate Mind dans Supabase.

    Stratégie fallback :
      1. Essaie de lire/écrire dans Supabase
      2. Si impossible (pas de connexion, DATABASE_URL absent, etc.) → CSV local
      3. Jamais de crash total — l'app continue toujours

    Usage type dans main_api.py :
        db = get_db()
        df = db.load_listings()          # remplace pd.read_csv(CLEAN_PATH)
        stats = db.upsert_listings(df)   # remplace df.to_csv(CLEAN_PATH)
    """

    def __init__(self):
        self._available = self._test_connection()

    def _test_connection(self) -> bool:
        """
        Teste la connexion Supabase au démarrage.
        Retourne True si OK, False si fallback CSV sera utilisé.
        """
        if not PSYCOPG2_AVAILABLE:
            logger.warning("[supabase] psycopg2 non installé → mode CSV")
            return False
        if not DATABASE_URL:
            logger.warning("[supabase] DATABASE_URL absent dans .env → mode CSV")
            logger.info("[supabase] ℹ️  Ajoutez DATABASE_URL dans votre fichier .env")
            return False
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    ver = cur.fetchone()[0]
                    logger.info(f"[supabase] ✅ Connecté à Supabase — {ver[:50]}")
            return True
        except Exception as e:
            logger.error(f"[supabase] ❌ Connexion échouée : {e}")
            logger.info("[supabase] → Fallback CSV activé")
            return False

    @property
    def is_available(self) -> bool:
        """True si Supabase est connecté, False si mode CSV fallback."""
        return self._available

    # ── Création des tables ──────────────────────────────────────────────────

    def ensure_tables(self) -> bool:
        """
        Crée les tables si elles n'existent pas (idempotent).
        À appeler une fois au démarrage ou lors du premier run pipeline.
        Retourne True si OK, False si erreur.
        """
        if not self._available:
            logger.info("[supabase] ensure_tables ignoré — mode CSV")
            return False

        DDL_LISTING = """
        CREATE TABLE IF NOT EXISTS listings (
            id               BIGSERIAL PRIMARY KEY,
            url              TEXT NOT NULL,
            source           TEXT NOT NULL,
            title            TEXT,
            price            NUMERIC(12,2),
            surface          NUMERIC(8,2),
            rooms            SMALLINT,
            property_type    TEXT,
            city             TEXT,
            governorate      TEXT,
            description      TEXT,
            latitude         DOUBLE PRECISION,
            longitude        DOUBLE PRECISION,
            publication_date TIMESTAMPTZ,
            price_per_m2     NUMERIC(10,2),
            trust_score      NUMERIC(5,3),
            trust_level      TEXT,
            legal_risk_score NUMERIC(5,3) DEFAULT 0.15,
            legal_risk_level TEXT DEFAULT 'Faible',
            has_title_deed   BOOLEAN DEFAULT FALSE,
            has_permit       BOOLEAN DEFAULT FALSE,
            nlp_enriched     BOOLEAN DEFAULT FALSE,
            ingested_at      TIMESTAMPTZ DEFAULT NOW(),
            updated_at       TIMESTAMPTZ DEFAULT NOW(),
            pipeline_version TEXT,
            data_hash        TEXT,
            CONSTRAINT uq_listing UNIQUE (url, source)
        );
        CREATE INDEX IF NOT EXISTS idx_listings_city ON listings(city);
        CREATE INDEX IF NOT EXISTS idx_listings_trust ON listings(trust_score DESC);
        CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price);
        CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source);
        CREATE INDEX IF NOT EXISTS idx_listings_ingested ON listings(ingested_at DESC);
        """

        DDL_PRICE_HISTORY = """
        CREATE TABLE IF NOT EXISTS price_history (
            id          BIGSERIAL PRIMARY KEY,
            listing_url TEXT NOT NULL,
            source      TEXT NOT NULL,
            old_price   NUMERIC(12,2),
            new_price   NUMERIC(12,2),
            change_pct  NUMERIC(7,2),
            changed_at  TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_ph_url ON price_history(listing_url, source);
        """

        DDL_PIPELINE_RUNS = """
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id               BIGSERIAL PRIMARY KEY,
            run_id           TEXT UNIQUE NOT NULL,
            started_at       TIMESTAMPTZ DEFAULT NOW(),
            finished_at      TIMESTAMPTZ,
            status           TEXT DEFAULT 'running',
            rows_in          INTEGER,
            rows_out         INTEGER,
            rows_inserted    INTEGER DEFAULT 0,
            rows_updated     INTEGER DEFAULT 0,
            rows_skipped     INTEGER DEFAULT 0,
            avg_trust_score  NUMERIC(5,3),
            suspect_count    INTEGER,
            sources_used     TEXT[],
            config           JSONB,
            error_message    TEXT
        );
        """

        DDL_PORTFOLIOS = """
        CREATE TABLE IF NOT EXISTS portfolios (
            id            BIGSERIAL PRIMARY KEY,
            user_id       TEXT NOT NULL,
            listing_url   TEXT NOT NULL,
            source        TEXT NOT NULL,
            saved_price   NUMERIC(12,2),
            title         TEXT,
            city          TEXT,
            property_type TEXT,
            surface       NUMERIC(8,2),
            trust_score   NUMERIC(5,3),
            saved_at      TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_portfolio UNIQUE (user_id, listing_url, source)
        );
        CREATE INDEX IF NOT EXISTS idx_portfolio_user ON portfolios(user_id);
        """

        DDL_SUBSCRIPTIONS = """
        CREATE TABLE IF NOT EXISTS alert_subscriptions (
            id              BIGSERIAL PRIMARY KEY,
            sub_id          TEXT UNIQUE NOT NULL,
            email           TEXT NOT NULL,
            name            TEXT,
            watch_zones     TEXT[],
            watch_cities    TEXT[],
            budget_max      NUMERIC(12,2),
            surface_min     NUMERIC(8,2),
            property_types  TEXT[],
            trust_min       NUMERIC(5,3) DEFAULT 0.70,
            price_threshold NUMERIC(5,3) DEFAULT 0.08,
            webhook_url     TEXT,
            active          BOOLEAN DEFAULT TRUE,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        );
        """

        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    for ddl in [DDL_LISTING, DDL_PRICE_HISTORY, DDL_PIPELINE_RUNS,
                                DDL_PORTFOLIOS, DDL_SUBSCRIPTIONS]:
                        cur.execute(ddl)
            logger.info("[supabase] ✅ Tables créées / vérifiées")
            return True
        except Exception as e:
            logger.error(f"[supabase] ensure_tables échoué : {e}")
            return False

    # ══════════════════════════════════════════════════════════════════════════
    # CHARGEMENT DES DONNÉES — remplace pd.read_csv(CLEAN_PATH)
    # ══════════════════════════════════════════════════════════════════════════

    def load_listings(
        self,
        city:          Optional[str]   = None,
        property_type: Optional[str]   = None,
        min_trust:     float           = 0.0,
        limit:         int             = 15000,
    ) -> Optional[pd.DataFrame]:
        """
        Charge les annonces depuis Supabase, avec fallback CSV.

        C'est LE remplacement de _df() dans main_api.py.
        La logique est exactement la même interface qu'avant — juste
        que les données viennent de Supabase au lieu du CSV.

        Args:
            city:          Filtre par ville (optionnel)
            property_type: Filtre par type de bien (optionnel)
            min_trust:     Trust score minimum (défaut 0 = tout)
            limit:         Nombre max de lignes (défaut 15 000)

        Returns:
            DataFrame ou None si aucune donnée disponible
        """
        # ── Essai Supabase ────────────────────────────────────────────────
        if self._available:
            try:
                filters = ["trust_score >= %s OR trust_score IS NULL"]
                params  = [min_trust]

                if city:
                    filters.append("LOWER(city) LIKE LOWER(%s)")
                    params.append(f"%{city}%")
                if property_type:
                    filters.append("property_type = %s")
                    params.append(property_type)

                params.append(limit)
                query = (
                    f"SELECT * FROM listings "
                    f"WHERE {' AND '.join(filters)} "
                    f"ORDER BY ingested_at DESC LIMIT %s"
                )

                with _get_conn() as conn:
                    df = pd.read_sql(query, conn, params=params)

                if df is not None and not df.empty:
                    logger.debug(f"[supabase] load_listings: {len(df)} lignes depuis Supabase")
                    return df
                else:
                    logger.info("[supabase] Supabase vide — fallback CSV")

            except Exception as e:
                logger.warning(f"[supabase] load_listings échoué ({e}) → fallback CSV")

        # ── Fallback CSV ──────────────────────────────────────────────────
        return self._load_from_csv(min_trust=min_trust)

    def _load_from_csv(self, min_trust: float = 0.0) -> Optional[pd.DataFrame]:
        """Charge depuis le CSV local — fallback si Supabase indisponible."""
        for path, sep in [(CLEAN_CSV, ","), (RAW_CSV, ";")]:
            if path.exists():
                try:
                    df = pd.read_csv(path, sep=sep, on_bad_lines="skip",
                                     encoding="utf-8", encoding_errors="replace")
                    if len(df) > 5:
                        logger.debug(f"[supabase] load CSV: {len(df)} lignes depuis {path.name}")
                        return df
                except Exception:
                    continue
        return None

    def load_territorial(self) -> Optional[pd.DataFrame]:
        """
        Charge les données pour l'analyse territoriale BO2.
        Utilise Supabase si disponible, sinon CSV avec prepare_temporal_data.
        """
        df = self.load_listings(limit=20000)
        if df is None:
            return None

        # Applique prepare_temporal_data si les colonnes temporelles manquent
        if "date" not in df.columns:
            try:
                from tools.territorial_tools import prepare_temporal_data
                df = prepare_temporal_data(df)
            except Exception as e:
                logger.warning(f"[supabase] prepare_temporal_data: {e}")
        return df

    # ══════════════════════════════════════════════════════════════════════════
    # UPSERT — remplace df.to_csv(CLEAN_PATH)
    # ══════════════════════════════════════════════════════════════════════════

    def upsert_listings(
        self,
        df:               pd.DataFrame,
        pipeline_version: str = "v3.2",
    ) -> dict:
        """
        Insère ou met à jour les annonces dans Supabase.

        Stratégie (garantit zéro doublon) :
          - (url, source) absent → INSERT
          - (url, source) présent + données changées → UPDATE + log price_history
          - (url, source) présent + données identiques → SKIP

        Si Supabase est indisponible → sauvegarde CSV local (comme avant).

        Returns:
            {"inserted": int, "updated": int, "skipped": int, "mode": "supabase"|"csv"}
        """
        if df.empty:
            return {"inserted": 0, "updated": 0, "skipped": 0, "mode": "empty"}

        # ── Essai Supabase ────────────────────────────────────────────────
        if self._available:
            try:
                stats  = {"inserted": 0, "updated": 0, "skipped": 0}
                now    = datetime.utcnow()

                with _get_conn() as conn:
                    with conn.cursor() as cur:
                        for _, row in df.iterrows():
                            url    = str(row.get("url", "")) or None
                            source = str(row.get("source", "unknown"))
                            if not url:
                                stats["skipped"] += 1
                                continue

                            data_hash = self._hash_row(row.to_dict())

                            cur.execute(
                                "SELECT id, price, data_hash FROM listings "
                                "WHERE url = %s AND source = %s",
                                (url, source)
                            )
                            existing = cur.fetchone()
                            row_data = self._build_row_data(row, source, url,
                                                            data_hash, now,
                                                            pipeline_version)

                            if existing is None:
                                # INSERT
                                row_data["ingested_at"] = now
                                cols = list(row_data.keys())
                                cur.execute(
                                    f"INSERT INTO listings ({', '.join(cols)}) "
                                    f"VALUES ({', '.join(['%s']*len(cols))})",
                                    [row_data[c] for c in cols]
                                )
                                stats["inserted"] += 1

                            elif existing[2] != data_hash:
                                # UPDATE — données changées
                                old_price = existing[1]
                                new_price = row_data.get("price")
                                if old_price and new_price and old_price != new_price:
                                    chg = round((new_price - old_price) / old_price * 100, 2)
                                    cur.execute(
                                        "INSERT INTO price_history "
                                        "(listing_url, source, old_price, new_price, change_pct) "
                                        "VALUES (%s, %s, %s, %s, %s)",
                                        (url, source, old_price, new_price, chg)
                                    )
                                update_cols = [c for c in row_data
                                               if c not in ("url", "source", "ingested_at")]
                                cur.execute(
                                    f"UPDATE listings SET "
                                    f"{', '.join(f'{c} = %s' for c in update_cols)} "
                                    f"WHERE url = %s AND source = %s",
                                    [row_data[c] for c in update_cols] + [url, source]
                                )
                                stats["updated"] += 1
                            else:
                                stats["skipped"] += 1

                logger.info(
                    f"[supabase] Upsert OK — "
                    f"insérés:{stats['inserted']} "
                    f"mis-à-jour:{stats['updated']} "
                    f"ignorés:{stats['skipped']}"
                )
                # Sauvegarde aussi le CSV (double sécurité)
                self._save_csv_backup(df)
                return {**stats, "mode": "supabase"}

            except Exception as e:
                logger.error(f"[supabase] upsert échoué ({e}) → fallback CSV")

        # ── Fallback CSV ──────────────────────────────────────────────────
        self._save_csv_backup(df)
        return {
            "inserted": len(df),
            "updated": 0,
            "skipped": 0,
            "mode": "csv_fallback"
        }

    def _save_csv_backup(self, df: pd.DataFrame) -> None:
        """Sauvegarde le CSV local — toujours fait pour garantir le fallback."""
        try:
            CLEAN_CSV.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(CLEAN_CSV, index=False)
            logger.debug(f"[supabase] CSV backup: {CLEAN_CSV}")
        except Exception as e:
            logger.warning(f"[supabase] CSV backup échoué: {e}")

    @staticmethod
    def _hash_row(row: dict) -> str:
        """SHA-256 court sur les champs clés — détecte les changements."""
        key = {k: row.get(k) for k in ["price", "surface", "description", "title"]}
        return hashlib.sha256(
            json.dumps(key, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

    @staticmethod
    def _build_row_data(row: pd.Series, source: str, url: str,
                        data_hash: str, now: datetime,
                        pipeline_version: str) -> dict:
        """Construit le dictionnaire de données pour INSERT/UPDATE."""
        def safe(col, default=None):
            val = row.get(col, default)
            try:
                if pd.isna(val):
                    return default
            except (TypeError, ValueError):
                pass
            return val

        price = safe("price")
        surf  = safe("surface")
        ppm2  = safe("price_per_m2")
        if not ppm2 and price and surf and float(surf) > 0:
            ppm2 = round(float(price) / float(surf), 2)

        return {
            "url":              url,
            "source":           source,
            "title":            safe("title"),
            "price":            price,
            "surface":          surf,
            "rooms":            safe("rooms"),
            "property_type":    safe("property_type"),
            "city":             safe("city"),
            "governorate":      safe("governorate"),
            "description":      str(safe("description", ""))[:2000],
            "latitude":         safe("latitude"),
            "longitude":        safe("longitude"),
            "publication_date": safe("publication_date"),
            "price_per_m2":     ppm2,
            "trust_score":      safe("trust_score"),
            "trust_level":      safe("trust_level"),
            "legal_risk_score": safe("legal_risk_score", 0.15),
            "legal_risk_level": safe("legal_risk_level", "Faible"),
            "has_title_deed":   bool(safe("has_title_deed", False)),
            "has_permit":       bool(safe("has_permit", False)),
            "nlp_enriched":     bool(safe("nlp_enriched", False)),
            "pipeline_version": pipeline_version,
            "data_hash":        data_hash,
            "updated_at":       now,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # PIPELINE RUNS TRACKING
    # ══════════════════════════════════════════════════════════════════════════

    def log_pipeline_run(
        self,
        run_id:        str,
        rows_in:       int,
        rows_out:      int,
        upsert_stats:  dict,
        avg_trust:     float,
        suspect_count: int,
        sources:       list,
        config:        dict,
        status:        str = "success",
        error_msg:     str = None,
    ) -> None:
        """Enregistre les métriques d'un run de pipeline."""
        if not self._available:
            logger.info(f"[supabase] log_pipeline_run ignoré (mode CSV) — run={run_id}")
            return
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO pipeline_runs (
                            run_id, finished_at, status,
                            rows_in, rows_out,
                            rows_inserted, rows_updated, rows_skipped,
                            avg_trust_score, suspect_count,
                            sources_used, config, error_message
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (run_id) DO UPDATE SET
                            finished_at = EXCLUDED.finished_at,
                            status      = EXCLUDED.status,
                            rows_out    = EXCLUDED.rows_out
                    """, (
                        run_id, datetime.utcnow(), status,
                        rows_in, rows_out,
                        upsert_stats.get("inserted", 0),
                        upsert_stats.get("updated", 0),
                        upsert_stats.get("skipped", 0),
                        avg_trust, suspect_count,
                        sources, json.dumps(config), error_msg,
                    ))
            logger.info(f"[supabase] Run {run_id} loggé — status={status}")
        except Exception as e:
            logger.warning(f"[supabase] log_pipeline_run échoué : {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # HISTORIQUE DES PRIX — alimente PriceHistory.tsx avec des données RÉELLES
    # ══════════════════════════════════════════════════════════════════════════

    def get_price_history(self, url: str, source: str = None) -> list[dict]:
        """
        Historique des prix pour une annonce.
        Retourne une liste vide si Supabase indisponible ou aucun historique.
        """
        if not self._available:
            return []
        try:
            with _get_conn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    q = ("SELECT old_price, new_price, change_pct, changed_at "
                         "FROM price_history WHERE listing_url = %s ")
                    p = [url]
                    if source:
                        q += "AND source = %s "
                        p.append(source)
                    q += "ORDER BY changed_at DESC LIMIT 50"
                    cur.execute(q, p)
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"[supabase] get_price_history: {e}")
            return []

    def get_dashboard_stats(self) -> dict:
        """
        Stats dashboard directement depuis Supabase (plus rapide que CSV).
        Fallback sur les stats CSV si indisponible.
        """
        if not self._available:
            return {}
        try:
            with _get_conn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute("""
                        SELECT
                            COUNT(*)                                               AS total,
                            ROUND(AVG(trust_score)::NUMERIC, 3)                   AS avg_trust,
                            SUM(CASE WHEN trust_score < 0.5 THEN 1 ELSE 0 END)    AS suspect_count,
                            SUM(CASE WHEN legal_risk_score >= 0.6 THEN 1 ELSE 0 END) AS high_legal,
                            MAX(ingested_at)                                       AS last_ingested
                        FROM listings
                    """)
                    row = cur.fetchone()
                    return dict(row) if row else {}
        except Exception as e:
            logger.warning(f"[supabase] get_dashboard_stats: {e}")
            return {}

    # ══════════════════════════════════════════════════════════════════════════
    # PORTFOLIO — remplace _portfolios: dict en RAM
    # ══════════════════════════════════════════════════════════════════════════

    def portfolio_get(self, user_id: str) -> list[dict]:
        """Récupère les favoris d'un utilisateur."""
        if not self._available:
            return []
        try:
            with _get_conn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM portfolios WHERE user_id = %s "
                        "ORDER BY saved_at DESC",
                        (user_id,)
                    )
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"[supabase] portfolio_get: {e}")
            return []

    def portfolio_add(self, user_id: str, item: dict) -> bool:
        """Ajoute un bien aux favoris. Retourne False si déjà présent."""
        if not self._available:
            return False
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO portfolios
                            (user_id, listing_url, source, saved_price,
                             title, city, property_type, surface, trust_score)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (user_id, listing_url, source) DO NOTHING
                    """, (
                        user_id,
                        item.get("url", ""),
                        item.get("source", "unknown"),
                        item.get("price"),
                        item.get("title"),
                        item.get("city"),
                        item.get("property_type"),
                        item.get("surface"),
                        item.get("trust_score"),
                    ))
            return True
        except Exception as e:
            logger.warning(f"[supabase] portfolio_add: {e}")
            return False

    def portfolio_remove(self, user_id: str, listing_url: str) -> bool:
        """Supprime un bien des favoris."""
        if not self._available:
            return False
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM portfolios WHERE user_id = %s AND listing_url = %s",
                        (user_id, listing_url)
                    )
            return True
        except Exception as e:
            logger.warning(f"[supabase] portfolio_remove: {e}")
            return False

    # ══════════════════════════════════════════════════════════════════════════
    # ABONNEMENTS / ALERTES — remplace SubscriptionStore (fichier JSON local)
    # ══════════════════════════════════════════════════════════════════════════

    def subscription_add(self, sub: dict) -> bool:
        """Crée un abonnement aux alertes."""
        if not self._available:
            return False
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO alert_subscriptions
                            (sub_id, email, name, watch_zones, watch_cities,
                             budget_max, surface_min, property_types, trust_min,
                             price_threshold, webhook_url)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (sub_id) DO NOTHING
                    """, (
                        sub.get("sub_id"),
                        sub.get("email"),
                        sub.get("name"),
                        sub.get("watch_zones", []),
                        sub.get("watch_cities", []),
                        sub.get("budget_max"),
                        sub.get("surface_min"),
                        sub.get("property_types", []),
                        sub.get("trust_min", 0.70),
                        sub.get("price_threshold", 0.08),
                        sub.get("webhook_url"),
                    ))
            return True
        except Exception as e:
            logger.warning(f"[supabase] subscription_add: {e}")
            return False

    def subscription_list_active(self) -> list[dict]:
        """Liste tous les abonnements actifs."""
        if not self._available:
            return []
        try:
            with _get_conn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM alert_subscriptions WHERE active = TRUE"
                    )
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"[supabase] subscription_list: {e}")
            return []

    def subscription_remove(self, email: str) -> bool:
        """Désactive un abonnement par email."""
        if not self._available:
            return False
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE alert_subscriptions SET active = FALSE WHERE email = %s",
                        (email,)
                    )
            return True
        except Exception as e:
            logger.warning(f"[supabase] subscription_remove: {e}")
            return False


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON — une seule instance partagée dans toute l'application
# ══════════════════════════════════════════════════════════════════════════════

_db_instance: Optional[SupabaseManager] = None


def get_db() -> SupabaseManager:
    """
    Retourne le singleton SupabaseManager.
    Crée l'instance à la première utilisation (lazy init).

    Usage dans main_api.py :
        from db.supabase_manager import get_db
        db = get_db()
        df = db.load_listings()
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = SupabaseManager()
    return _db_instance
