"""
Estate Mind — live_stats.py
============================
Lit les vraies statistiques depuis Supabase avec les bons noms de colonnes.
Schema réel : price, surface, rooms, city, governorate, property_type,
              trust_score, trust_level, source, url, latitude, longitude

Utilisé par /api/live-stats dans main_api.py
"""
from __future__ import annotations
import warnings
from pathlib import Path
warnings.filterwarnings("ignore")


def get_live_stats(db_url: str) -> dict:
    """
    Lit directement via psycopg2 avec les vrais noms de colonnes.
    Retourne un dict complet pour alimenter le frontend.
    """
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        cur  = conn.cursor()

        # ── Total annonces ────────────────────────────────────────────────────
        cur.execute("SELECT COUNT(*) FROM listings")
        total = cur.fetchone()[0]

        # ── Annonces avec prix renseigné ──────────────────────────────────────
        cur.execute("SELECT COUNT(*) FROM listings WHERE price IS NOT NULL AND price > 0")
        with_price = cur.fetchone()[0]

        # ── Trust score ───────────────────────────────────────────────────────
        cur.execute("SELECT AVG(trust_score) FROM listings WHERE trust_score IS NOT NULL")
        avg_trust = float(cur.fetchone()[0] or 0)

        cur.execute("SELECT COUNT(*) FROM listings WHERE trust_score IS NOT NULL AND trust_score >= 0.75")
        n_fiable = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM listings WHERE trust_score IS NOT NULL AND trust_score >= 0.50 AND trust_score < 0.75")
        n_moyen  = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM listings WHERE trust_score IS NOT NULL AND trust_score < 0.50")
        n_suspect = cur.fetchone()[0]

        # ── Sources ───────────────────────────────────────────────────────────
        cur.execute("""
            SELECT source, COUNT(*) as n
            FROM listings
            WHERE source IS NOT NULL
            GROUP BY source
            ORDER BY n DESC
        """)
        sources = {r[0]: r[1] for r in cur.fetchall()}

        # ── Types de bien ─────────────────────────────────────────────────────
        cur.execute("""
            SELECT property_type, COUNT(*) as n
            FROM listings
            WHERE property_type IS NOT NULL AND property_type != ''
            GROUP BY property_type
            ORDER BY n DESC
            LIMIT 8
        """)
        property_types = {r[0]: r[1] for r in cur.fetchall()}

        # ── Villes ────────────────────────────────────────────────────────────
        cur.execute("""
            SELECT city, COUNT(*) as n,
                   AVG(CASE WHEN price > 0 AND surface > 0 THEN price/surface END) as avg_ppm2
            FROM listings
            WHERE city IS NOT NULL AND city != ''
            GROUP BY city
            ORDER BY n DESC
            LIMIT 20
        """)
        cities = [
            {
                "city": r[0],
                "n":    r[1],
                "ppm2": round(float(r[2]), 0) if r[2] else None,
            }
            for r in cur.fetchall()
        ]

        # ── Prix médian national ──────────────────────────────────────────────
        cur.execute("""
            SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price/NULLIF(surface,0))
            FROM listings
            WHERE price > 0 AND surface > 0 AND price/surface BETWEEN 100 AND 15000
        """)
        national_median_ppm2 = cur.fetchone()[0]
        national_median_ppm2 = round(float(national_median_ppm2), 0) if national_median_ppm2 else None

        # ── Annonces récentes (10 dernières) ──────────────────────────────────
        cur.execute("""
            SELECT url, source, title, price, surface, city, property_type,
                   trust_score, trust_level, latitude, longitude
            FROM listings
            WHERE title IS NOT NULL AND title != ''
            ORDER BY id DESC
            LIMIT 10
        """)
        cols_recent = ["url","source","title","price","surface","city",
                       "property_type","trust_score","trust_level","latitude","longitude"]
        recent = []
        for r in cur.fetchall():
            row = dict(zip(cols_recent, r))
            if row.get("price") and row.get("surface") and row["surface"] > 0:
                row["price_per_m2"] = round(float(row["price"]) / float(row["surface"]), 0)
            recent.append(row)

        # ── Anomalies ─────────────────────────────────────────────────────────
        cur.execute("SELECT COUNT(*) FROM listings WHERE trust_score IS NOT NULL AND trust_score < 0.40")
        n_anomalies = cur.fetchone()[0]

        cur.close()
        conn.close()

        return {
            "status":              "live",
            "source":              "supabase",
            "total":               total,
            "with_price":          with_price,
            "avg_trust":           round(avg_trust, 3),
            "n_fiable":            n_fiable,
            "n_moyen":             n_moyen,
            "n_suspect":           n_suspect,
            "n_anomalies":         n_anomalies,
            "national_median_ppm2": national_median_ppm2,
            "sources":             sources,
            "property_types":      property_types,
            "cities":              cities,
            "recent_listings":     recent,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}
