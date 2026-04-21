"""
Estate Mind — Cleaning Tools v2.1
Fonctions de nettoyage appelées par le Collector Agent et inject_csv.py.

Corrections v2.1 :
  - normalize_columns : couvre tous les formats réels des scrapers
    * annonces_combined.csv : price_value, surface_m2, bedrooms
    * Mubawab scraper brut  : price_text, surface_text, rooms_text, type_bien
    * Tayara scraper brut   : price, surface_m2, bedrooms
    * Tecnocasa scraper brut: price_numeric, surface_numeric, rooms_numeric
    * Remax scraper brut    : ListingPrice, TotalArea, TotalNumOfRooms
  - clean_price : extrait les nombres depuis price_text ("450 000 DT", etc.)
"""
import re
import pandas as pd
import numpy as np
from loguru import logger
from config.settings import (
    MIN_PRICE, MAX_PRICE, MIN_SURFACE, MAX_SURFACE, PRICE_OUTLIER_FACTOR
)


STANDARD_COLUMNS = [
    "source", "title", "price", "surface", "rooms", "property_type",
    "city", "governorate", "latitude", "longitude",
    "description", "publication_date", "url"
]

PROPERTY_TYPE_MAP = {
    r"appart|apt|appartement":          "appartement",
    r"villa|villas":                    "villa",
    r"maison|house":                    "maison",
    r"terrain|land|lot":                "terrain",
    r"bureau|office|local commercial":  "bureau_local",
    r"studio":                          "studio",
    r"immeuble|building":               "immeuble",
    r"ferme|farm|agricole":             "ferme",
}

GOVERNORATE_MAP = {
    "tunis": "Tunis", "ariana": "Ariana", "ben arous": "Ben Arous",
    "manouba": "Manouba", "nabeul": "Nabeul", "zaghouan": "Zaghouan",
    "bizerte": "Bizerte", "beja": "Béja", "jendouba": "Jendouba",
    "kef": "Le Kef", "siliana": "Siliana", "sousse": "Sousse",
    "monastir": "Monastir", "mahdia": "Mahdia", "sfax": "Sfax",
    "kairouan": "Kairouan", "kasserine": "Kasserine", "sidi bouzid": "Sidi Bouzid",
    "gabes": "Gabès", "medenine": "Médenine", "tataouine": "Tataouine",
    "gafsa": "Gafsa", "tozeur": "Tozeur", "kebili": "Kébili",
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise toutes les colonnes vers le schéma unifié STANDARD_COLUMNS.

    Gère les formats de tous les scrapers Estate Mind :
      - annonces_combined.csv  → price_value, surface_m2, bedrooms, region
      - Mubawab scraper brut   → price_text, surface_text, rooms_text, type_bien
      - Tayara scraper brut    → price (déjà ok), surface_m2, bedrooms
      - Tecnocasa scraper brut → price_numeric, surface_numeric, rooms_numeric
      - Remax scraper brut     → ListingPrice, TotalArea, TotalNumOfRooms
    """
    df = df.copy()

    # ── PRIX ─────────────────────────────────────────────────────────────────
    # Priorité : price_value > price_numeric > ListingPrice > price_text > price
    if "price" not in df.columns or df["price"].isna().all():
        for src_col in ["price_value", "price_numeric", "ListingPrice", "price_text"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["price"] = df[src_col]
                break
    # Si price existe déjà mais est vide, essayer les alternatives
    elif df["price"].isna().mean() > 0.5:
        for src_col in ["price_value", "price_numeric", "ListingPrice", "price_text"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["price"] = df["price"].fillna(df[src_col])

    # ── SURFACE ───────────────────────────────────────────────────────────────
    if "surface" not in df.columns or df["surface"].isna().all():
        for src_col in ["surface_m2", "surface_numeric", "TotalArea", "LivingArea",
                        "surface_text", "area"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["surface"] = df[src_col]
                break
    elif df["surface"].isna().mean() > 0.5:
        for src_col in ["surface_m2", "surface_numeric", "TotalArea", "surface_text"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["surface"] = df["surface"].fillna(df[src_col])

    # ── PIÈCES ────────────────────────────────────────────────────────────────
    if "rooms" not in df.columns or df["rooms"].isna().all():
        for src_col in ["rooms_numeric", "TotalNumOfRooms", "rooms_text",
                        "bedrooms", "NumberOfBedrooms"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["rooms"] = df[src_col]
                break
    elif df["rooms"].isna().mean() > 0.5:
        for src_col in ["rooms_numeric", "TotalNumOfRooms", "bedrooms"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["rooms"] = df["rooms"].fillna(df[src_col])

    # ── TYPE DE BIEN ──────────────────────────────────────────────────────────
    if "property_type" not in df.columns or df["property_type"].isna().all():
        for src_col in ["type_bien", "category", "PropertyTypeUID", "CommPropertyType"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["property_type"] = df[src_col]
                break
    elif df["property_type"].isna().mean() > 0.5:
        for src_col in ["type_bien", "category"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["property_type"] = df["property_type"].fillna(df[src_col])

    # ── VILLE ─────────────────────────────────────────────────────────────────
    if "city" not in df.columns or df["city"].isna().all():
        for src_col in ["City", "city_name", "ville", "Ville", "Province",
                        "LocalZone", "location_raw"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["city"] = df[src_col]
                break

    # ── GOUVERNORAT ───────────────────────────────────────────────────────────
    if "governorate" not in df.columns or df["governorate"].isna().all():
        for src_col in ["region", "gouvernorat", "Gouvernorat", "RegionalZone",
                        "Province", "province_name", "region_name"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["governorate"] = df[src_col]
                break
    elif df["governorate"].isna().mean() > 0.5:
        for src_col in ["region", "RegionalZone", "Province"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["governorate"] = df["governorate"].fillna(df[src_col])

    # ── COORDONNÉES GPS ───────────────────────────────────────────────────────
    if "latitude" not in df.columns or df["latitude"].isna().all():
        for src_col in ["Latitude", "lat"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["latitude"] = df[src_col]; break
    if "longitude" not in df.columns or df["longitude"].isna().all():
        for src_col in ["Longitude", "lon"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["longitude"] = df[src_col]; break

    # ── TITRE ─────────────────────────────────────────────────────────────────
    if "title" not in df.columns or df["title"].isna().all():
        for src_col in ["Titre", "titre", "Title", "TitleAddress"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["title"] = df[src_col]; break

    # ── DESCRIPTION ───────────────────────────────────────────────────────────
    if "description" not in df.columns or df["description"].isna().all():
        for src_col in ["Description", "desc", "Description_fr"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["description"] = df[src_col]; break

    # ── URL ───────────────────────────────────────────────────────────────────
    if "url" not in df.columns or df["url"].isna().all():
        for src_col in ["Lien", "lien", "URL", "url_direct", "url_guess",
                        "detail_url", "ListingKey"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["url"] = df[src_col]; break

    # ── DATE ──────────────────────────────────────────────────────────────────
    if "publication_date" not in df.columns or df["publication_date"].isna().all():
        for src_col in ["scraped_at", "FirstUpdatedToWeb", "published_on",
                        "OrigListingDate", "detail_published_on", "Date", "date"]:
            if src_col in df.columns and df[src_col].notna().any():
                df["publication_date"] = df[src_col]; break

    # ── SOURCE ────────────────────────────────────────────────────────────────
    if "source" not in df.columns:
        df["source"] = "inconnu"

    # ── Remplir les colonnes manquantes avec NaN ──────────────────────────────
    for col in STANDARD_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan

    return df[STANDARD_COLUMNS].copy()


def clean_price(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nettoie et transforme la colonne price.
    Gère les formats texte ("450 000 DT", "1.2 million TND", "Prix à consulter").
    """
    def _parse(val):
        if pd.isna(val):
            return np.nan

        s = str(val).lower().strip()

        # Valeurs non-numériques explicites
        if any(x in s for x in ["demande", "négociable", "negociable",
                                  "contact", "sur demande", "consulter",
                                  "appel", "à voir", "a voir"]):
            return np.nan

        # Nettoyage
        s = (s.replace("tnd", "").replace(" dt", "").replace("dt", "")
              .replace("\xa0", "").replace(" ", "").replace(",", ""))

        if "million" in s:
            nums = re.findall(r"\d+\.?\d*", s)
            return float(nums[0]) * 1_000_000 if nums else np.nan

        if s.endswith("k"):
            nums = re.findall(r"\d+\.?\d*", s)
            return float(nums[0]) * 1_000 if nums else np.nan

        nums = re.findall(r"\d+\.?\d*", s)
        if not nums:
            return np.nan
        v = float(nums[0])
        # Si la valeur semble en milliers (ex: Mubawab stocke parfois 450 pour 450 000)
        # On garde tel quel — le filtre MIN_PRICE/MAX_PRICE tranchera
        return v

    df["price"] = df["price"].apply(_parse)
    logger.info(f"[clean_price] Valeurs non nulles : {df['price'].notna().sum()}")

    before = len(df)
    df = df[df["price"].between(MIN_PRICE, MAX_PRICE) | df["price"].isna()]
    removed = before - len(df)
    if removed:
        logger.info(f"[clean_price] Prix hors limites supprimés : {removed}")

    return df


def clean_surface(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoie et filtre la colonne surface. Gère les formats texte ('120 m²', etc.)"""
    def _parse(val):
        if pd.isna(val):
            return np.nan
        s = re.sub(r"[^\d.]", "", str(val).replace(",", "."))
        try:
            return float(s)
        except ValueError:
            return np.nan

    df["surface"] = df["surface"].apply(_parse)
    df = df[(df["surface"].between(MIN_SURFACE, MAX_SURFACE)) | df["surface"].isna()]
    return df


def clean_rooms(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise le nombre de pièces. Gère les formats texte ('3 pièces', etc.)"""
    def _parse(val):
        if pd.isna(val):
            return np.nan
        # Extraire le premier nombre
        nums = re.findall(r"\d+", str(val))
        if not nums:
            return np.nan
        v = int(nums[0])
        return v if 0 < v <= 20 else np.nan

    df["rooms"] = df["rooms"].apply(_parse)
    return df


def normalize_property_type(df: pd.DataFrame) -> pd.DataFrame:
    """Mappe les types de biens vers un vocabulaire contrôlé."""
    def _map(val):
        if pd.isna(val):
            return "autre"
        v = str(val).lower().strip()
        for pattern, label in PROPERTY_TYPE_MAP.items():
            if re.search(pattern, v):
                return label
        return "autre"

    df["property_type"] = df["property_type"].apply(_map)
    return df


def normalize_location(df: pd.DataFrame) -> pd.DataFrame:
    """Standardise governorate + city."""
    def _gov(val):
        if pd.isna(val):
            return np.nan
        v = str(val).lower().strip()
        for key, label in GOVERNORATE_MAP.items():
            if key in v:
                return label
        return str(val).strip().title()

    def _city(val):
        if pd.isna(val):
            return np.nan
        v = str(val).strip().title()
        return v if v.lower() not in ("nan", "none", "unknown", "") else np.nan

    df["governorate"] = df["governorate"].apply(_gov)
    df["city"] = df["city"].apply(_city)
    return df


def clean_text_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoie title et description (HTML, espaces, encodage)."""
    def _clean(val):
        if pd.isna(val):
            return ""
        s = str(val)
        s = re.sub(r"<[^>]+>", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    df["title"] = df["title"].apply(_clean)
    df["description"] = df["description"].apply(_clean)
    return df


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Supprime les doublons par URL, puis par similarité clé."""
    before = len(df)

    # Déduplication exacte sur URL
    df = df.drop_duplicates(subset=["url"], keep="first")

    # Déduplication sur combinaison clé — seulement si les colonnes sont remplies
    key_cols = ["price", "surface", "city", "property_type"]
    if all(df[c].notna().any() for c in key_cols):
        df = df.drop_duplicates(
            subset=key_cols,
            keep="first"
        )

    removed = before - len(df)
    logger.info(f"Doublons supprimés : {removed}")
    return df.reset_index(drop=True)


def remove_outliers_iqr(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Supprime les outliers via méthode IQR."""
    if col not in df.columns or df[col].dropna().empty:
        return df

    q1 = df[col].quantile(0.25)
    q3 = df[col].quantile(0.75)
    iqr = q3 - q1

    if pd.isna(iqr) or iqr == 0:
        return df

    lower = q1 - PRICE_OUTLIER_FACTOR * iqr
    upper = q3 + PRICE_OUTLIER_FACTOR * iqr
    mask = df[col].between(lower, upper) | df[col].isna()
    removed = (~mask).sum()

    if removed:
        logger.info(f"Outliers supprimés dans '{col}' : {removed}")

    return df[mask].reset_index(drop=True)


def compute_price_per_m2(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute la colonne price_per_m2."""
    df["price_per_m2"] = np.where(
        (df["surface"] > 0) & (df["price"].notna()),
        (df["price"] / df["surface"]).round(2),
        np.nan
    )
    return df


def run_full_cleaning(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pipeline complet de nettoyage — appelé par CollectorAgent et inject_csv.py.

    Étapes :
      1. normalize_columns  → schéma unifié 13 colonnes (gère tous les scrapers)
      2. clean_price        → parse les formats texte, filtre les aberrants
      3. clean_surface      → parse les formats texte, filtre les aberrants
      4. clean_rooms        → parse les formats texte
      5. normalize_property_type → vocabulaire contrôlé
      6. normalize_location      → standardise ville / gouvernorat
      7. clean_text_fields       → nettoie HTML, espaces
      8. remove_duplicates       → dédup URL + combinaison clé
      9. remove_outliers_iqr     → IQR sur price et surface
      10. compute_price_per_m2   → ajoute la colonne calculée
    """
    logger.info(f"Nettoyage démarré — {len(df)} lignes en entrée")

    df = normalize_columns(df)
    df = clean_price(df)
    df = clean_surface(df)
    df = clean_rooms(df)
    df = normalize_property_type(df)
    df = normalize_location(df)
    df = clean_text_fields(df)
    df = remove_duplicates(df)
    df = remove_outliers_iqr(df, "price")
    df = remove_outliers_iqr(df, "surface")
    df = compute_price_per_m2(df)

    # Rapport de qualité
    for col in ["price", "surface", "rooms", "property_type", "city"]:
        if col in df.columns:
            pct = df[col].notna().mean() * 100
            logger.info(f"  {col}: {df[col].notna().sum()}/{len(df)} ({pct:.0f}%)")

    logger.info(f"Nettoyage terminé — {len(df)} lignes en sortie")
    return df
