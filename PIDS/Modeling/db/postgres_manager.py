"""
Estate Mind — PostgreSQL Manager (Cloud)
═════════════════════════════════════════
Gère la persistance des annonces dans PostgreSQL cloud
(Supabase / Neon / Railway — même protocole PostgreSQL standard).

Fonctionnalités :
  - Création automatique des tables si absentes
  - Upsert sans redondance (ON CONFLICT DO NOTHING sur url + source)
  - Versioning des prix : chaque changement de prix est tracké
  - Requêtes analytiques (stats marché, top suspects, etc.)

Connexion :
  Mettre DATABASE_URL dans .env :
    Supabase  → Settings > Database > Connection string (URI mode)
    Neon      → Dashboard > Connection Details > Connection string
    Railway   → Variables > DATABASE_URL
"""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from datetime import datetime
from typing import Generator, Optional

import pandas as pd
import psycopg2
import psycopg2.extras
from loguru import logger

from config.settings import PG_URL


# ══════════════════════════════════════════════════════════════════════════════
# DDL — schéma des tables
# ══════════════════════════════════════════════════════════════════════════════

DDL_LISTINGS = """
CREATE TABLE IF NOT EXISTS listings (
    id               SERIAL PRIMARY KEY,

    -- Clé de déduplication
    url              TEXT        NOT NULL,
    source           TEXT        NOT NULL,

    -- Champs principaux
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

    -- Champs calculés par le pipeline
    price_per_m2     NUMERIC(10,2),
    trust_score      NUMERIC(5,3),
    trust_level      TEXT,
    legal_risk_score NUMERIC(5,3),
    legal_risk_level TEXT,

    -- Champs NLP
    has_title_deed   BOOLEAN DEFAULT FALSE,
    has_permit       BOOLEAN DEFAULT FALSE,
    nlp_enriched     BOOLEAN DEFAULT FALSE,

    -- Métadonnées pipeline
    ingested_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    pipeline_version TEXT,
    data_hash        TEXT,       -- hash du contenu pour détecter les changements

    -- Contrainte de déduplication
    CONSTRAINT uq_listing UNIQUE (url, source)
);

-- Index pour les requêtes fréquentes
CREATE INDEX IF NOT EXISTS idx_listings_city          ON listings(city);
CREATE INDEX IF NOT EXISTS idx_listings_governorate   ON listings(governorate);
CREATE INDEX IF NOT EXISTS idx_listings_property_type ON listings(property_type);
CREATE INDEX IF NOT EXISTS idx_listings_trust_score   ON listings(trust_score);
CREATE INDEX IF NOT EXISTS idx_listings_ingested_at   ON listings(ingested_at);
CREATE INDEX IF NOT EXISTS idx_listings_price         ON listings(price);
"""

DDL_PRICE_HISTORY = """
CREATE TABLE IF NOT EXISTS price_history (
    id          SERIAL PRIMARY KEY,
    listing_url TEXT        NOT NULL,
    source      TEXT        NOT NULL,
    old_price   NUMERIC(12,2),
    new_price   NUMERIC(12,2),
    changed_at  TIMESTAMPTZ DEFAULT NOW(),
    change_pct  NUMERIC(7,2)   -- variation en %
);
CREATE INDEX IF NOT EXISTS idx_price_history_url ON price_history(listing_url, source);
"""

DDL_PIPELINE_RUNS = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id               SERIAL PRIMARY KEY,
    run_id           TEXT UNIQUE NOT NULL,
    started_at       TIMESTAMPTZ DEFAULT NOW(),
    finished_at      TIMESTAMPTZ,
    status           TEXT DEFAULT 'running',  -- running | success | failed
    rows_in          INTEGER,
    rows_out         INTEGER,
    rows_inserted    INTEGER,
    rows_updated     INTEGER,
    rows_skipped     INTEGER,
    avg_trust_score  NUMERIC(5,3),
    suspect_count    INTEGER,
    high_legal_count INTEGER,
    sources_used     TEXT[],
    config           JSONB,       -- hyperparamètres utilisés
    error_message    TEXT
);
"""


# ══════════════════════════════════════════════════════════════════════════════
# CONNEXION
# ══════════════════════════════════════════════════════════════════════════════

@contextmanager
def _get_conn() -> Generator:
    """Context manager pour connexion PostgreSQL avec auto-close."""
    conn = None
    try:
        conn = psycopg2.connect(PG_URL, connect_timeout=10)
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"[postgres] Erreur connexion : {e}")
        raise
    finally:
        if conn:
            conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# MANAGER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class PostgresManager:
    """
    Interface haut-niveau pour les opérations PostgreSQL d'Estate Mind.

    Usage :
        pg = PostgresManager()
        pg.ensure_tables()
        stats = pg.upsert_listings(df_clean, pipeline_version="v2.1")
        print(stats)  # {"inserted": 1203, "updated": 45, "skipped": 892}
    """

    def __init__(self, pg_url: str = PG_URL):
        self.pg_url = pg_url
        self._test_connection()

    def _test_connection(self) -> None:
        """Vérifie la connexion au démarrage."""
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    ver = cur.fetchone()[0]
                    logger.info(f"[postgres] ✅ Connecté — {ver[:40]}")
        except Exception as e:
            logger.error(f"[postgres] ❌ Connexion impossible : {e}")
            logger.error("[postgres] Vérifiez DATABASE_URL dans votre .env")
            raise

    def ensure_tables(self) -> None:
        """Crée les tables si elles n'existent pas (idempotent)."""
        with _get_conn() as conn:
            with conn.cursor() as cur:
                for ddl in [DDL_LISTINGS, DDL_PRICE_HISTORY, DDL_PIPELINE_RUNS]:
                    cur.execute(ddl)
        logger.info("[postgres] Tables vérifiées / créées")

    # ── Hachage pour détecter les changements ────────────────────────────────

    @staticmethod
    def _hash_row(row: dict) -> str:
        """SHA-256 des champs principaux — détecte si l'annonce a changé."""
        key_fields = {k: row.get(k) for k in ["price", "surface", "description", "title"]}
        content    = json.dumps(key_fields, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    # ── Upsert principal ──────────────────────────────────────────────────────

    def upsert_listings(
        self,
        df: pd.DataFrame,
        pipeline_version: str = "v2",
    ) -> dict:
        """
        Insère ou met à jour les annonces sans créer de doublons.

        Stratégie :
          - Si (url, source) n'existe pas → INSERT
          - Si existe ET data_hash différent (prix/desc changé) → UPDATE + log dans price_history
          - Si existe ET data_hash identique → SKIP (aucune modification)

        Returns:
            {"inserted": int, "updated": int, "skipped": int}
        """
        if df.empty:
            return {"inserted": 0, "updated": 0, "skipped": 0}

        stats     = {"inserted": 0, "updated": 0, "skipped": 0}
        now       = datetime.utcnow()

        # Colonnes disponibles dans le DataFrame
        available_cols = set(df.columns)

        def safe(row: pd.Series, col: str, default=None):
            val = row.get(col, default)
            if pd.isna(val) if not isinstance(val, str) else False:
                return default
            return val

        with _get_conn() as conn:
            with conn.cursor() as cur:

                for _, row in df.iterrows():
                    url    = str(row.get("url", "")) or None
                    source = str(row.get("source", "unknown"))

                    if not url:
                        stats["skipped"] += 1
                        continue

                    data_hash = self._hash_row(row.to_dict())

                    # Vérifie si l'annonce existe déjà
                    cur.execute(
                        "SELECT id, price, data_hash FROM listings WHERE url = %s AND source = %s",
                        (url, source)
                    )
                    existing = cur.fetchone()

                    row_data = {
                        "url":              url,
                        "source":           source,
                        "title":            safe(row, "title"),
                        "price":            safe(row, "price"),
                        "surface":          safe(row, "surface"),
                        "rooms":            safe(row, "rooms"),
                        "property_type":    safe(row, "property_type"),
                        "city":             safe(row, "city"),
                        "governorate":      safe(row, "governorate"),
                        "description":      str(safe(row, "description", ""))[:2000],
                        "latitude":         safe(row, "latitude"),
                        "longitude":        safe(row, "longitude"),
                        "publication_date": safe(row, "publication_date"),
                        "price_per_m2":     safe(row, "price_per_m2"),
                        "trust_score":      safe(row, "trust_score"),
                        "trust_level":      safe(row, "trust_level"),
                        "legal_risk_score": safe(row, "legal_risk_score"),
                        "legal_risk_level": safe(row, "legal_risk_level"),
                        "has_title_deed":   bool(safe(row, "has_title_deed", False)),
                        "has_permit":       bool(safe(row, "has_permit", False)),
                        "nlp_enriched":     bool(safe(row, "nlp_enriched", False)),
                        "pipeline_version": pipeline_version,
                        "data_hash":        data_hash,
                        "updated_at":       now,
                    }

                    if existing is None:
                        # ── INSERT ──────────────────────────────────────────
                        row_data["ingested_at"] = now
                        cols = list(row_data.keys())
                        vals = [row_data[c] for c in cols]
                        cur.execute(
                            f"INSERT INTO listings ({', '.join(cols)}) "
                            f"VALUES ({', '.join(['%s']*len(cols))})",
                            vals
                        )
                        stats["inserted"] += 1

                    elif existing[2] != data_hash:
                        # ── UPDATE (données changées) ────────────────────
                        old_price = existing[1]
                        new_price = row_data.get("price")

                        # Log du changement de prix
                        if old_price and new_price and old_price != new_price:
                            change_pct = round((new_price - old_price) / old_price * 100, 2)
                            cur.execute(
                                "INSERT INTO price_history (listing_url, source, old_price, new_price, change_pct) "
                                "VALUES (%s, %s, %s, %s, %s)",
                                (url, source, old_price, new_price, change_pct)
                            )

                        update_cols = [c for c in row_data if c not in ("url", "source", "ingested_at")]
                        cur.execute(
                            f"UPDATE listings SET {', '.join(f'{c} = %s' for c in update_cols)} "
                            f"WHERE url = %s AND source = %s",
                            [row_data[c] for c in update_cols] + [url, source]
                        )
                        stats["updated"] += 1

                    else:
                        # ── SKIP (aucun changement) ──────────────────────
                        stats["skipped"] += 1

        logger.info(
            f"[postgres] Upsert terminé — "
            f"insérés: {stats['inserted']}, "
            f"mis à jour: {stats['updated']}, "
            f"ignorés: {stats['skipped']}"
        )
        return stats

    # ── Pipeline runs tracking ────────────────────────────────────────────────

    def log_pipeline_run(
        self,
        run_id:          str,
        rows_in:         int,
        rows_out:        int,
        upsert_stats:    dict,
        avg_trust:       float,
        suspect_count:   int,
        high_legal:      int,
        sources:         list[str],
        config:          dict,
        status:          str = "success",
        error_message:   str = None,
    ) -> None:
        """Enregistre les métriques d'un run de pipeline pour traçabilité."""
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pipeline_runs (
                        run_id, finished_at, status,
                        rows_in, rows_out,
                        rows_inserted, rows_updated, rows_skipped,
                        avg_trust_score, suspect_count, high_legal_count,
                        sources_used, config, error_message
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    avg_trust, suspect_count, high_legal,
                    sources, json.dumps(config), error_message,
                ))
        logger.info(f"[postgres] Run {run_id} loggé — status={status}")

    # ── Requêtes analytiques ──────────────────────────────────────────────────

    def get_market_stats(
        self,
        city:          Optional[str] = None,
        property_type: Optional[str] = None,
    ) -> dict:
        """Stats de marché directement depuis PostgreSQL."""
        filters, params = [], []
        if city:
            filters.append("LOWER(city) = LOWER(%s)"); params.append(city)
        if property_type:
            filters.append("property_type = %s"); params.append(property_type)

        where = f"WHERE {' AND '.join(filters)}" if filters else ""

        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT
                        COUNT(*)                    AS total,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price)       AS median_price,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_per_m2) AS median_ppm2,
                        AVG(trust_score)            AS avg_trust,
                        SUM(CASE WHEN trust_score < 0.5 THEN 1 ELSE 0 END) AS suspects,
                        SUM(CASE WHEN legal_risk_score >= 0.6 THEN 1 ELSE 0 END) AS high_legal
                    FROM listings {where}
                """, params)
                return dict(cur.fetchone())

    def get_top_suspects(self, limit: int = 20) -> list[dict]:
        """Récupère les annonces les plus suspectes."""
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT title, city, price, trust_score, legal_risk_score, url, source
                    FROM listings
                    WHERE trust_score IS NOT NULL
                    ORDER BY trust_score ASC
                    LIMIT %s
                """, (limit,))
                return [dict(r) for r in cur.fetchall()]

    def get_price_history(self, url: str, source: str) -> list[dict]:
        """Historique des prix pour une annonce."""
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT old_price, new_price, change_pct, changed_at
                    FROM price_history
                    WHERE listing_url = %s AND source = %s
                    ORDER BY changed_at DESC
                """, (url, source))
                return [dict(r) for r in cur.fetchall()]

    def load_to_dataframe(
        self,
        city:          Optional[str] = None,
        property_type: Optional[str] = None,
        min_trust:     float = 0.0,
        limit:         int   = 10000,
    ) -> pd.DataFrame:
        """Charge les données depuis PostgreSQL vers un DataFrame."""
        filters, params = ["trust_score >= %s"], [min_trust]
        if city:
            filters.append("LOWER(city) = LOWER(%s)"); params.append(city)
        if property_type:
            filters.append("property_type = %s"); params.append(property_type)

        params.append(limit)
        with _get_conn() as conn:
            return pd.read_sql(
                f"SELECT * FROM listings WHERE {' AND '.join(filters)} "
                f"ORDER BY trust_score DESC LIMIT %s",
                conn, params=params
            )
