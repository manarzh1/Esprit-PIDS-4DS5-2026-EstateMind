"""
Estate Mind — fix_tecnocasa_update.py
UPDATE des lignes Tecnocasa existantes (pas d'INSERT, pas de ON CONFLICT).
Colonnes réelles Supabase : price, surface, rooms, city, governorate, etc.
"""
import sys, warnings
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

# ── Colonnes réelles Supabase (lues depuis les logs) ─────────────────────────
# id, url, source, title, price, surface, rooms, property_type, city,
# governorate, description, latitude, longitude, publication_date,
# price_per_m2, trust_score, trust_level, legal_risk_score, legal_risk_level,
# has_title_deed, has_permit, nlp_enriched, ingested_at, updated_at,
# pipeline_version, data_hash

def load_tecnocasa() -> pd.DataFrame:
    files = sorted(RAW_DIR.glob("tecnocasa_*.csv"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    dfs = []
    for f in files:
        for enc in ["utf-8", "utf-8-sig", "latin1"]:
            try:
                df = pd.read_csv(f, encoding=enc, on_bad_lines="skip", low_memory=False)
                df = df[[c for c in df.columns if not str(c).startswith("Unnamed")]]
                if len(df) > 0:
                    dfs.append(df)
                    logger.info(f"   ✅ {f.name} — {len(df)} lignes")
                    break
            except Exception:
                continue
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)
    df = df.loc[:, ~df.columns.duplicated(keep='first')]
    logger.info(f"Total brut : {len(df)} lignes")
    return df


def parse_url(url: str):
    parts = str(url).rstrip("/").split("/")
    city, ptype = "", "autre"
    for i, p in enumerate(parts):
        if p in ("vendre", "louer", "acheter", "location"):
            if i + 1 < len(parts): ptype = parts[i + 1]
            if i + 3 < len(parts): city  = parts[i + 3].replace("-", " ").title()
            elif i + 2 < len(parts): city = parts[i + 2].replace("-", " ").title()
            break
    type_norm = {
        "appartement":"appartement","villa":"villa","terrain":"terrain",
        "maison":"maison","bureau":"bureau_local","local":"bureau_local",
        "immeuble":"immeuble","studio":"studio","ferme":"ferme",
    }
    return city, type_norm.get(ptype.lower(), "autre")


def build_df(raw: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame()

    # URL
    df["url"] = raw.get("detail_url", raw.get("url", pd.Series(dtype=str))).astype(str)

    # City + type depuis URL
    parsed        = df["url"].apply(parse_url)
    url_city      = parsed.apply(lambda x: x[0])
    url_type      = parsed.apply(lambda x: x[1])

    # Prix → colonne Supabase = "price"
    pc = next((c for c in ["price_numeric","price"] if c in raw.columns), None)
    df["price"] = pd.to_numeric(raw[pc], errors="coerce") if pc else np.nan

    # Surface → "surface"
    sc = next((c for c in ["surface_numeric","surface"] if c in raw.columns), None)
    df["surface"] = pd.to_numeric(raw[sc], errors="coerce") if sc else np.nan

    # Chambres → "rooms"
    rc = next((c for c in ["rooms_numeric","rooms","bedrooms"] if c in raw.columns), None)
    df["rooms"] = pd.to_numeric(raw[rc], errors="coerce") if rc else np.nan

    # City → "city"
    city_raw  = raw.get("city_name", raw.get("city", pd.Series(dtype=str))).fillna("").astype(str)
    df["city"] = city_raw.where(city_raw.str.strip() != "", url_city)

    # Gouvernorat → "governorate"
    gov_raw = raw.get("province_name", raw.get("region_name", pd.Series(dtype=str))).fillna("").astype(str)
    df["governorate"] = gov_raw.where(gov_raw.str.strip() != "", "")

    # Type de bien → "property_type"
    df["property_type"] = url_type

    # Description
    df["description"] = raw.get("description", raw.get("subtitle", pd.Series(dtype=str))).fillna("").astype(str)

    # Title
    df["title"] = raw.get("title", pd.Series(dtype=str)).fillna("").astype(str)

    # GPS
    df["latitude"]  = pd.to_numeric(raw["lat"], errors="coerce") if "lat" in raw.columns else np.nan
    df["longitude"] = pd.to_numeric(raw["lon"], errors="coerce") if "lon" in raw.columns else np.nan

    # Prix/m²
    df["price_per_m2"] = (df["price"] / df["surface"].replace(0, np.nan)).round(2)

    # Trust score
    try:
        from tools.risk_tools import run_trust_scoring
        tmp = df.copy()
        df = run_trust_scoring(tmp)
        logger.info("[Trust] OK")
    except Exception as e:
        logger.warning(f"[Trust] {e}")

    # Nettoyer
    df = df[df["url"].notna() & (df["url"].astype(str).str.strip() != "")]
    df = df.drop_duplicates(subset=["url"], keep="first")

    # Aperçu
    logger.info(f"✅ {len(df)} lignes prêtes")
    logger.info(f"Aperçu :\n{df[['url','price','surface','city','property_type']].head(3).to_string()}")
    return df


def update_rows(df: pd.DataFrame, conn) -> int:
    """UPDATE listings SET ... WHERE url = %s"""
    
    # Colonnes à mettre à jour (celles qui existent dans df ET dans Supabase)
    update_cols = [c for c in [
        "source", "title", "description", "price", "surface", "rooms",
        "property_type", "city", "governorate", "latitude", "longitude",
        "price_per_m2", "trust_score", "trust_level",
    ] if c in df.columns]

    set_clause = ", ".join([f"{c} = %s" for c in update_cols])
    sql = f"UPDATE listings SET {set_clause} WHERE url = %s"

    cur  = conn.cursor()
    n_ok = 0; n_err = 0; n_notfound = 0

    for _, row in df.iterrows():
        vals = []
        for c in update_cols:
            v = row[c]
            if isinstance(v, float) and np.isnan(v):   v = None
            elif isinstance(v, np.floating):            v = float(v)
            elif isinstance(v, np.integer):             v = int(v)
            elif isinstance(v, np.bool_):               v = bool(v)
            vals.append(v)
        vals.append(str(row["url"]))  # WHERE url = ?

        try:
            cur.execute(sql, vals)
            if cur.rowcount == 0:
                n_notfound += 1  # URL pas dans Supabase → on peut INSERT après
            else:
                n_ok += 1
        except Exception as e:
            n_err += 1
            conn.rollback()
            if n_err <= 3:
                logger.warning(f"Erreur : {e}")
            continue

        if (n_ok + n_notfound) % 200 == 0:
            conn.commit()
            logger.info(f"   {n_ok} mis à jour, {n_notfound} non trouvés, {n_err} erreurs...")

    conn.commit()
    cur.close()
    logger.info(f"[UPDATE] ✅ {n_ok} mis à jour | {n_notfound} non trouvés | {n_err} erreurs")

    # Si des URLs ne sont pas dans Supabase → INSERT simple
    if n_notfound > 0:
        not_found_mask = []
        cur2 = conn.cursor()
        for _, row in df.iterrows():
            cur2.execute("SELECT 1 FROM listings WHERE url = %s LIMIT 1", (str(row["url"]),))
            not_found_mask.append(cur2.fetchone() is None)
        cur2.close()
        
        to_insert = df[not_found_mask]
        if not to_insert.empty:
            logger.info(f"[INSERT] {len(to_insert)} nouvelles lignes à insérer...")
            insert_cols = ["url", "source"] + update_cols
            insert_cols = list(dict.fromkeys(insert_cols))  # dédupliquer
            col_str     = ", ".join(insert_cols)
            ph          = ", ".join(["%s"] * len(insert_cols))
            sql_ins     = f"INSERT INTO listings ({col_str}) VALUES ({ph})"

            cur3 = conn.cursor()
            n_ins = 0
            for _, row in to_insert.iterrows():
                vals = []
                for c in insert_cols:
                    v = row.get(c, None)
                    if isinstance(v, float) and np.isnan(v):  v = None
                    elif isinstance(v, np.floating):           v = float(v)
                    elif isinstance(v, np.integer):            v = int(v)
                    vals.append(v)
                try:
                    cur3.execute(sql_ins, vals)
                    n_ins += 1
                except Exception as e:
                    if n_ins < 3:
                        logger.warning(f"INSERT : {e}")
            conn.commit()
            cur3.close()
            logger.info(f"[INSERT] ✅ {n_ins} nouvelles lignes insérées")
            n_ok += n_ins

    return n_ok


if __name__ == "__main__":
    logger.info("\n" + "═"*60)
    logger.info("  Fix Tecnocasa — UPDATE direct par url")
    logger.info("═"*60)

    try:
        from config.settings import PG_URL
        import psycopg2
        conn = psycopg2.connect(PG_URL)
        logger.info("[DB] ✅ Connecté")
    except Exception as e:
        logger.error(f"Connexion : {e}")
        sys.exit(1)

    raw = load_tecnocasa()
    if raw.empty:
        sys.exit(1)

    df = build_df(raw)
    t0 = datetime.now()
    n  = update_rows(df, conn)
    conn.close()

    logger.info(f"\n✅ {n} Tecnocasa mises à jour en {round((datetime.now()-t0).total_seconds(),1)}s")
