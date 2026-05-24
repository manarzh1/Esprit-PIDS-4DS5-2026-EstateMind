"""
Estate Mind — Multi-Source Connectors (v2 — mappings réels)
"""
from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger

from config.settings import RAW_CSV_PATH, MAX_PAGES_PER_SOURCE

UNIFIED_SCHEMA = [
    "source", "title", "price", "surface", "rooms",
    "property_type", "city", "governorate",
    "description", "url", "publication_date",
    "latitude", "longitude",
]

REMAX_TYPE_MAP = {
    1:"appartement",2:"villa",3:"maison",4:"terrain",5:"bureau_local",
    6:"immeuble",7:"ferme",8:"studio",9:"appartement",10:"villa",11:"terrain",
}

MUBAWAB_TYPE_MAP = {
    "appartement":"appartement","villa":"villa","maison":"maison","terrain":"terrain",
    "bureau":"bureau_local","local commercial":"bureau_local","studio":"studio",
    "immeuble":"immeuble","ferme":"ferme","duplex":"villa","penthouse":"villa",
}

TECNO_TYPE_MAP = {
    "appartement":"appartement","villa":"villa","maison":"maison","terrain":"terrain",
    "bureau":"bureau_local","commerce":"bureau_local","studio":"studio",
    "immeuble":"immeuble","ferme":"ferme","duplex":"villa",
}

SOURCE_PRIORITY = {"remax":1,"tecnocasa":2,"mubawab":3,"tayara":4,"csv":5}


def _parse_price_text(text):
    if not text or str(text).strip() in ("","nan","None"): return None
    t = str(text).lower().strip()
    t = t.replace("tnd","").replace(" dt","").replace("dt","")
    t = t.replace("\xa0","").replace(" ","").replace(",",".")
    if "million" in t:
        m = re.search(r"([\d.]+)", t)
        return float(m.group(1))*1_000_000 if m else None
    if "k" in t:
        m = re.search(r"([\d.]+)", t)
        return float(m.group(1))*1_000 if m else None
    m = re.search(r"([\d.]+)", t)
    try: return float(m.group(1)) if m else None
    except: return None

def _parse_surface_text(text):
    if not text or str(text).strip() in ("","nan","None"): return None
    t = str(text).lower().replace("m²","").replace("m2","").replace("sqm","")
    t = t.replace("\xa0","").replace(" ","")
    m = re.search(r"([\d.]+)", t)
    try: return float(m.group(1)) if m else None
    except: return None

def _parse_rooms_text(text):
    if not text or str(text).strip() in ("","nan","None"): return None
    t = str(text).strip()
    m_sn = re.search(r"[Ss]\+\s*(\d)", t)
    if m_sn: return int(m_sn.group(1))+1
    m_num = re.search(r"(\d+)", t)
    if m_num: return int(m_num.group(1))
    return None

def _map_type(raw, type_map):
    if not raw: return "autre"
    v = str(raw).lower().strip()
    for key, label in type_map.items():
        if key in v: return label
    return "autre"

def _enforce_schema(df, source_name):
    df = df.copy()
    df["source"] = source_name
    for col in UNIFIED_SCHEMA:
        if col not in df.columns: df[col] = None
    return df[UNIFIED_SCHEMA].copy()

def _latest_csv(pattern, raw_dir):
    files = sorted(raw_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


class BaseConnector(ABC):
    DEFAULT_DELAY_SECONDS = 1.5
    DEFAULT_MAX_PAGES = 10
    RETRY_ATTEMPTS = 3

    def __init__(self, delay=None, max_pages=None):
        self.delay = delay or self.DEFAULT_DELAY_SECONDS
        self.max_pages = max_pages or self.DEFAULT_MAX_PAGES
        self.name = self.__class__.__name__.replace("Connector","").lower()

    @abstractmethod
    def fetch(self, max_pages=None): ...

    @abstractmethod
    def normalize(self, df_raw): ...

    def run(self, max_pages=None):
        pages = max_pages or self.max_pages
        logger.info(f"[{self.name}] Démarrage (max_pages={pages})")
        t0 = time.time()
        for attempt in range(1, self.RETRY_ATTEMPTS+1):
            try:
                df_raw = self.fetch(pages)
                if df_raw.empty:
                    logger.warning(f"[{self.name}] Aucune donnée")
                    return pd.DataFrame(columns=UNIFIED_SCHEMA)
                df_norm = self.normalize(df_raw)
                df_out  = _enforce_schema(df_norm, self.name)
                logger.info(f"[{self.name}] OK {len(df_out)} annonces en {round(time.time()-t0,1)}s")
                return df_out
            except Exception as e:
                logger.warning(f"[{self.name}] Tentative {attempt}/{self.RETRY_ATTEMPTS}: {e}")
                if attempt < self.RETRY_ATTEMPTS: time.sleep(self.delay*attempt)
        logger.error(f"[{self.name}] Echec")
        return pd.DataFrame(columns=UNIFIED_SCHEMA)


class TayaraConnector(BaseConnector):
    """
    Wrape TayaraScraper depuis scrapers/tayara_scraper_optimized.py.
    API: scraper.run_initial() -> (List[Dict], state)
         scraper.run_update(state) -> (List[Dict], state)
    Colonnes clés: url, title, description, price, city, surface_m2,
                   bedrooms, property_type, published_on, rooms_text
    """
    DEFAULT_DELAY_SECONDS = 0.3
    DEFAULT_MAX_PAGES = 10

    def __init__(self, mode="update", **kwargs):
        super().__init__(**kwargs)
        self.mode = mode

    def fetch(self, max_pages=None):
        from scrapers.tayara_scraper_optimized import (
            TayaraConfig, TayaraScraper, load_state, save_state
        )
        pages = max_pages or self.max_pages
        cfg = TayaraConfig(max_pages=pages, sleep_sec=self.delay,
                           scrape_detail=True, workers=4)
        scraper = TayaraScraper(cfg)
        state   = load_state(cfg)
        if self.mode == "initial" or not state.get("last_published_epoch"):
            rows, new_state = scraper.run_initial()
        else:
            rows, new_state = scraper.run_update(state)
        save_state(cfg, new_state)
        logger.info(f"[tayara] {len(rows)} lignes brutes")
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def normalize(self, df):
        rename = {
            "url":"url","title":"title","description":"description",
            "price":"price","city":"city","surface_m2":"surface",
            "bedrooms":"rooms","property_type":"property_type",
            "published_on":"publication_date",
        }
        df = df.rename(columns={k:v for k,v in rename.items() if k in df.columns})
        # Surface fallback
        if "surface" not in df.columns or df["surface"].isna().all():
            if "surface_m2_text" in df.columns:
                df["surface"] = df["surface_m2_text"].apply(_parse_surface_text)
        # Rooms fallback
        if "rooms" not in df.columns or df["rooms"].isna().all():
            if "rooms_text" in df.columns:
                df["rooms"] = df["rooms_text"].apply(_parse_rooms_text)
        # Price si textuel
        if "price" in df.columns and df["price"].dtype == object:
            df["price"] = df["price"].apply(_parse_price_text)
        # property_type
        if "property_type" in df.columns:
            df["property_type"] = df["property_type"].apply(lambda v: _map_type(v, MUBAWAB_TYPE_MAP))
        df["governorate"] = None
        df["latitude"]    = None
        df["longitude"]   = None
        return df


class MubawabConnector(BaseConnector):
    """
    Wrape mubawab_scraper.py.
    API: run_initial(max_pages) -> Path CSV
         run_update(max_pages)  -> Path CSV ou None
    Colonnes CSV (Listing dataclass): title, price_text, city, surface_text,
    rooms_text, type_bien, url, description, latitude, longitude, surface_habitable
    """
    DEFAULT_DELAY_SECONDS = 1.0
    DEFAULT_MAX_PAGES = 5

    def __init__(self, mode="update", **kwargs):
        super().__init__(**kwargs)
        self.mode = mode

    def fetch(self, max_pages=None):
        import scrapers.mubawab_scraper as mub
        pages = max_pages or self.max_pages
        if self.mode == "initial":
            csv_path = mub.run_initial(max_pages=pages)
        else:
            csv_path = mub.run_update(max_pages=pages)
        if csv_path is None or not Path(csv_path).exists():
            logger.info("[mubawab] Aucun nouveau CSV")
            return pd.DataFrame()
        df = pd.read_csv(csv_path, encoding="utf-8")
        logger.info(f"[mubawab] {len(df)} lignes")
        return df

    def normalize(self, df):
        rename = {
            "title":"title","url":"url","description":"description",
            "city":"city","latitude":"latitude","longitude":"longitude",
        }
        df = df.rename(columns={k:v for k,v in rename.items() if k in df.columns})
        if "price_text" in df.columns:
            df["price"] = df["price_text"].apply(_parse_price_text)
        # surface
        if "surface_habitable" in df.columns and df["surface_habitable"].notna().any():
            df["surface"] = df["surface_habitable"].apply(_parse_surface_text)
        elif "surface_text" in df.columns:
            df["surface"] = df["surface_text"].apply(_parse_surface_text)
        # rooms
        if "rooms_text" in df.columns:
            df["rooms"] = df["rooms_text"].apply(_parse_rooms_text)
        elif "bedrooms_text" in df.columns:
            df["rooms"] = df["bedrooms_text"].apply(_parse_rooms_text)
        # property_type
        tcol = "type_bien" if ("type_bien" in df.columns and df["type_bien"].notna().any()) else "property_type"
        if tcol in df.columns:
            df["property_type"] = df[tcol].apply(lambda v: _map_type(v, MUBAWAB_TYPE_MAP))
        else:
            df["property_type"] = "autre"
        df["governorate"]     = None
        df["publication_date"] = None
        return df


class TecnocasaConnector(BaseConnector):
    """
    Wrape tecnocasa_scraper.py.
    API: scrape_tecnocasa(mode, max_pages) -> Path CSV
    Colonnes CSV: title, price_numeric, surface_numeric, rooms_numeric,
    property_type_slug, city_name, province_name, detail_url,
    description, lat, lon, scraped_at
    """
    DEFAULT_DELAY_SECONDS = 1.0
    DEFAULT_MAX_PAGES = None

    def __init__(self, mode="update", **kwargs):
        super().__init__(**kwargs)
        self.mode = mode

    def fetch(self, max_pages=None):
        from scrapers.tecnocasa_scraper import scrape_tecnocasa
        pages = max_pages or self.max_pages
        logger.info(f"[tecnocasa] Mode {self.mode} (max_pages={pages})")
        csv_path = scrape_tecnocasa(mode=self.mode, max_pages=pages)
        if not csv_path or not Path(csv_path).exists():
            return pd.DataFrame()
        df = pd.read_csv(csv_path, encoding="utf-8")
        logger.info(f"[tecnocasa] {len(df)} lignes")
        return df

    def normalize(self, df):
        rename = {
            "title":"title","description":"description",
            "price_numeric":"price","surface_numeric":"surface",
            "rooms_numeric":"rooms","city_name":"city",
            "province_name":"governorate","detail_url":"url",
            "lat":"latitude","lon":"longitude","scraped_at":"publication_date",
        }
        df = df.rename(columns={k:v for k,v in rename.items() if k in df.columns})
        # URL relative -> absolue
        if "url" in df.columns:
            df["url"] = df["url"].apply(
                lambda v: f"https://www.tecnocasa.tn{v}"
                if isinstance(v,str) and v.startswith("/") else v
            )
        # property_type
        tcol = "property_type_slug" if "property_type_slug" in df.columns else "property_type"
        if tcol in df.columns:
            df["property_type"] = df[tcol].apply(lambda v: _map_type(v, TECNO_TYPE_MAP))
        else:
            df["property_type"] = "autre"
        return df


class RemaxConnector(BaseConnector):
    """
    Wrape remax_search_api.py.
    API: run_initial(max_pages, sleep_s)                  -> None (ecrit CSV)
         run_update(max_pages, sleep_s, seen_streak_stop) -> None (ecrit CSV)
    CSV généré: data/raw/remax_{initial|update}_TIMESTAMP.csv
    Colonnes CSV: TitleAddress, FullAddress, ListingPrice, TotalArea,
    TotalNumOfRooms, PropertyTypeUID, City, Province,
    Description_fr, Latitude, Longitude, LastUpdatedOnWeb, ListingId
    """
    DEFAULT_DELAY_SECONDS = 0.3
    DEFAULT_MAX_PAGES = 50
    RAW_DIR = Path("data") / "raw"

    def __init__(self, mode="update", **kwargs):
        super().__init__(**kwargs)
        self.mode = mode

    def fetch(self, max_pages=None):
        import scrapers.remax_search_api as remax
        pages = max_pages or self.max_pages
        if self.mode == "initial":
            remax.run_initial(max_pages=pages, sleep_s=self.delay)
        else:
            remax.run_update(max_pages=pages, sleep_s=self.delay, seen_streak_stop=3)
        prefix = "remax_initial_" if self.mode == "initial" else "remax_update_"
        csv_path = _latest_csv(f"{prefix}*.csv", self.RAW_DIR)
        if csv_path is None:
            logger.warning("[remax] Aucun CSV trouvé dans data/raw/")
            return pd.DataFrame()
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
        logger.info(f"[remax] {len(df)} lignes depuis {csv_path.name}")
        return df

    def normalize(self, df):
        rename = {
            "City":"city","Province":"governorate",
            "ListingPrice":"price","TotalArea":"surface",
            "TotalNumOfRooms":"rooms","Description_fr":"description",
            "Latitude":"latitude","Longitude":"longitude",
            "LastUpdatedOnWeb":"publication_date",
        }
        df = df.rename(columns={k:v for k,v in rename.items() if k in df.columns})
        # Titre
        if "TitleAddress" in df.columns and df["TitleAddress"].notna().any():
            df["title"] = df["TitleAddress"]
        elif "FullAddress" in df.columns:
            df["title"] = df["FullAddress"]
        else:
            df["title"] = "Bien immobilier Remax"
        # URL
        base = "https://www.remax.com.tn/listings/"
        id_col = "ListingId" if "ListingId" in df.columns else ("ListingKey" if "ListingKey" in df.columns else None)
        if id_col:
            df["url"] = df[id_col].apply(lambda lid: f"{base}{lid}" if pd.notna(lid) else None)
        # Surface fallback LivingArea
        if "surface" not in df.columns or df["surface"].isna().all():
            if "LivingArea" in df.columns:
                df["surface"] = pd.to_numeric(df["LivingArea"], errors="coerce")
        # PropertyTypeUID -> vocabulaire contrôlé
        if "PropertyTypeUID" in df.columns:
            df["property_type"] = df["PropertyTypeUID"].apply(
                lambda v: REMAX_TYPE_MAP.get(int(v),"autre") if pd.notna(v) else "autre"
            )
        else:
            df["property_type"] = "autre"
        # Coordonnées 0.0 = absentes
        for coord in ["latitude","longitude"]:
            if coord in df.columns:
                df[coord] = pd.to_numeric(df[coord], errors="coerce").replace(0.0, None)
        return df


class CSVConnector(BaseConnector):
    """Lit le CSV combiné existant (fallback / données historiques)."""
    def __init__(self, csv_path=RAW_CSV_PATH, **kwargs):
        super().__init__(**kwargs)
        self.csv_path = csv_path

    def fetch(self, max_pages=None):
        p = Path(self.csv_path)
        if not p.exists():
            logger.warning(f"[csv] Introuvable : {self.csv_path}")
            return pd.DataFrame()
        df = pd.read_csv(self.csv_path, encoding="latin-1", on_bad_lines="skip")
        logger.info(f"[csv] {len(df)} lignes")
        return df

    def normalize(self, df):
        rename = {
            "Type_Bien":"property_type","type_bien":"property_type",
            "Prix_TND":"price","Prix":"price","prix":"price",
            "Surface_m2":"surface","Surface":"surface",
            "Pieces":"rooms","pieces":"rooms",
            "Ville":"city","ville":"city",
            "Gouvernorat":"governorate","gouvernorat":"governorate",
            "Titre":"title","titre":"title",
            "Description":"description",
            "Lien":"url","lien":"url","URL":"url",
            "Date":"publication_date","Lat":"latitude","Lon":"longitude",
        }
        return df.rename(columns={k:v for k,v in rename.items() if k in df.columns})


class ConnectorRegistry:
    """
    Orchestre les 4 connecteurs (Tayara, Mubawab, Tecnocasa, Remax) + CSV fallback.

    Priorité de source en cas de doublon :
        remax(1) > tecnocasa(2) > mubawab(3) > tayara(4) > csv(5)

    Déduplication :
        - Primaire  : url (la plus fiable)
        - Secondaire: (price, surface, city) pour les annonces sans URL
    """
    def __init__(self, mode="update", max_pages=MAX_PAGES_PER_SOURCE,
                 dedup_on=None, delay=1.0):
        self.mode = mode
        self.max_pages = max_pages
        self.delay = delay
        self.dedup_on = dedup_on or ["url"]
        self._connectors = [
            TayaraConnector(mode=mode,    max_pages=max_pages, delay=0.3),
            MubawabConnector(mode=mode,   max_pages=max_pages, delay=1.0),
            TecnocasaConnector(mode=mode, max_pages=max_pages, delay=1.0),
            RemaxConnector(mode=mode,     max_pages=max_pages, delay=0.3),
            CSVConnector(),
        ]

    def register(self, connector):
        self._connectors.append(connector)

    def ingest_all(self, max_pages=None):
        pages  = max_pages or self.max_pages
        frames = []
        for conn in self._connectors:
            logger.info(f"[Registry] -> {conn.name}")
            df = conn.run(max_pages=pages)
            if not df.empty: frames.append(df)
            time.sleep(self.delay)
        if not frames:
            logger.error("[Registry] Aucune source")
            return pd.DataFrame(columns=UNIFIED_SCHEMA)
        combined = pd.concat(frames, ignore_index=True)
        before   = len(combined)
        combined["_p"] = combined["source"].map(SOURCE_PRIORITY).fillna(99)
        combined = combined.sort_values("_p")
        has_url  = combined["url"].notna() & (combined["url"] != "")
        df_u = combined[has_url].drop_duplicates(subset=["url"], keep="first")
        df_n = combined[~has_url].drop_duplicates(
            subset=["price","surface","city"], keep="first")
        combined = pd.concat([df_u, df_n], ignore_index=True).drop(columns=["_p"])
        logger.info(f"[Registry] {len(combined)} annonces uniques ({before-len(combined)} doublons)")
        return combined.reset_index(drop=True)

    @property
    def active_sources(self):
        return [c.name for c in self._connectors]
