# tecnocasa_scraper.py
# Méthode :
# 1) scrape /api/estates/search (pages) -> annonces + ids
# 2) call /api/estates/search-map-list UNE FOIS par (région, contrat)
# 3) pour CHAQUE annonce, visiter detail_url (HTML) et extraire la description (template slot estate-description)
#    + fallback si le template n’existe pas (paragraphes avant "REF.:")
# 4) merge lat/lon via {id -> (lat, lon)} puis write CSV unique dans data/raw (avec date)
# 5) mode update = ignore les ids déjà présents dans data/raw/tecnocasa_*.csv (PAS de JSON state)

import csv
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ==========================
#  Config générale
# ==========================

BASE_SEARCH_URL = "https://www.tecnocasa.tn/api/estates/search"
BASE_MAP_URL = "https://www.tecnocasa.tn/api/estates/search-map-list"
BASE_SITE_URL = "https://www.tecnocasa.tn/"

RAW_DIR = Path("data") / "raw"

API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.tecnocasa.tn/",
    "X-Requested-With": "XMLHttpRequest",
}

HTML_HEADERS = {
    "User-Agent": API_HEADERS["User-Agent"],
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Referer": "https://www.tecnocasa.tn/",
}

# ✅ IMPORTANT : Tecnocasa utilise "locazi" pour la location
CONTRACTS = {
    "sale": "acquis",   # vente
    "rent": "locazi",   # location ✅
}

# Provinces & régions Tecno
REGIONS = [
    {"region_id": "ne", "region_name": "Nord-Est (NE)",   "province_id": "GT", "province_name": "Grand Tunis", "placeholder": "Grand Tunis (provincia)"},
    {"region_id": "ce", "region_name": "Centre-Est (CE)", "province_id": "SS", "province_name": "Sousse",      "placeholder": "Sousse (provincia)"},
    {"region_id": "ce", "region_name": "Centre-Est (CE)", "province_id": "MS", "province_name": "Monastir",    "placeholder": "Monastir (provincia)"},
    {"region_id": "ce", "region_name": "Centre-Est (CE)", "province_id": "MH", "province_name": "Mahdia",      "placeholder": "Mahdia (provincia)"},
    {"region_id": "ce", "region_name": "Centre-Est (CE)", "province_id": "SF", "province_name": "Sfax",        "placeholder": "Sfax (provincia)"},
    {"region_id": "ne", "region_name": "Nord-Est (NE)",   "province_id": "BZ", "province_name": "Bizerte",     "placeholder": "Bizerte (provincia)"},
    {"region_id": "ne", "region_name": "Nord-Est (NE)",   "province_id": "NB", "province_name": "Cap Bon",     "placeholder": "Cap Bon (provincia)"},
    {"region_id": "ce", "region_name": "Centre-Est (CE)", "province_id": "KA", "province_name": "Kairouan",   "placeholder": "Kairouan (provincia)"},
]


# ==========================
#  Helpers
# ==========================

def ensure_raw_dir() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def safe_get_json(url: str, params: Dict[str, str]) -> Optional[dict]:
    try:
        resp = requests.get(url, headers=API_HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"[ERROR] GET {url} with {params} failed: {exc}")
        return None


def safe_get_html(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, headers=HTML_HEADERS, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        print(f"[WARN] HTML GET failed: {url} -> {exc}")
        return None


def extract_coords_from_map(data: dict) -> Dict[int, Tuple[Optional[float], Optional[float]]]:
    """
    Extrait {estate_id: (lat, lon)} depuis GeoJSON.
    GeoJSON coordinates = [lon, lat]
    """
    if not data:
        return {}

    features = None
    if isinstance(data, dict):
        if isinstance(data.get("features"), list):
            features = data["features"]
        elif isinstance(data.get("collection"), dict) and isinstance(data["collection"].get("features"), list):
            features = data["collection"]["features"]
        elif isinstance(data.get("data"), dict) and isinstance(data["data"].get("features"), list):
            features = data["data"]["features"]
        elif isinstance(data.get("data"), list):
            features = data["data"]

    if not features:
        return {}

    coords: Dict[int, Tuple[Optional[float], Optional[float]]] = {}
    for feat in features:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}

        eid = props.get("id") or feat.get("id")
        if eid is None:
            continue

        if geom.get("type") != "Point":
            continue

        coordinates = geom.get("coordinates") or []
        if len(coordinates) < 2:
            continue

        lon, lat = coordinates[0], coordinates[1]
        try:
            coords[int(eid)] = (float(lat), float(lon))
        except Exception:
            continue

    return coords


def parse_property_type(detail_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Déduit (type_slug, contract_slug) à partir de l'URL détail.
    Exemple: /vendre/appartement/grand-tunis/rades/63212.html
             -> type_slug = 'appartement', contract_slug = 'vendre'
    """
    try:
        parts = (detail_url or "").split("/")
        type_slug = parts[4] if len(parts) > 4 else None
        contract_slug = parts[3] if len(parts) > 3 else None
        return type_slug, contract_slug
    except Exception:
        return None, None


def normalize_price(price_str: Optional[str]) -> Optional[float]:
    if not price_str:
        return None
    try:
        clean = price_str.replace("DT", "").replace("dt", "")
        clean = clean.replace(" ", "").replace("\xa0", "")
        return float(clean)
    except Exception:
        return None


def normalize_surface(surface_str: Optional[str]) -> Optional[float]:
    if not surface_str:
        return None
    try:
        clean = surface_str.lower().replace("m²", "").replace("m2", "")
        clean = clean.replace(" ", "").replace("\xa0", "")
        return float(clean)
    except Exception:
        return None


def normalize_rooms(rooms_str: Optional[str]) -> Optional[int]:
    if not rooms_str:
        return None
    try:
        num = rooms_str.split()[0]
        return int(num)
    except Exception:
        return None


def load_existing_ids() -> set:
    """
    Charge tous les listing_id déjà présents dans les fichiers tecnocasa_*.csv
    de data/raw (pour le mode update).
    """
    seen = set()
    if not RAW_DIR.exists():
        return seen

    for path in RAW_DIR.glob("tecnocasa_*.csv"):
        try:
            with path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rid = row.get("listing_id")
                    if not rid:
                        continue
                    try:
                        seen.add(int(rid))
                    except ValueError:
                        seen.add(rid)
        except Exception as exc:
            print(f"[WARN] Impossible de lire {path}: {exc}")

    return seen


def normalize_detail_url(detail_url: Optional[str]) -> Optional[str]:
    if not detail_url:
        return None
    if detail_url.startswith("http://") or detail_url.startswith("https://"):
        return detail_url
    return urljoin(BASE_SITE_URL, detail_url.lstrip("/"))


def extract_description_from_html(html: str) -> Optional[str]:
    """
    ✅ Ce que tu veux (priorité) :
    <template slot="estate-description"> ... <p>...</p> ... </template>

    Fallback :
    - récupérer les paragraphes "principaux" de la page jusqu'à "REF.:"
    """
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # 1) PRIORITÉ : template slot="estate-description"
    tpl = soup.find("template", attrs={"slot": "estate-description"})
    if tpl:
        # Le contenu peut être interprétable par BeautifulSoup même dans <template>
        tpl_soup = BeautifulSoup(tpl.decode_contents() or "", "html.parser")
        paras = [p.get_text(" ", strip=True) for p in tpl_soup.find_all("p")]
        paras = [p for p in paras if p and len(p) >= 20]
        if paras:
            return "\n".join(paras).strip()

        # fallback simple si pas de <p>
        txt = tpl_soup.get_text("\n", strip=True)
        if txt and len(txt) >= 30:
            return re.sub(r"\n{3,}", "\n\n", txt).strip()

    # 2) FALLBACK : zone avant REF
    text = soup.get_text("\n", strip=True)
    if not text:
        return None

    # couper au niveau de "REF" (ex: "REF.:" ou "REF:")
    mref = re.search(r"\bREF\.?\s*:", text, flags=re.IGNORECASE)
    if mref:
        text = text[: mref.start()].strip()

    # filtrer un peu (enlever lignes de navigation/footer si présentes)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # on garde les lignes "longues" qui ressemblent à une description
    long_lines = []
    for ln in lines:
        if any(bad in ln.lower() for bad in ["données personnelles", "informations sur les cookies", "tecnocasa dans le monde"]):
            continue
        if len(ln) >= 60:
            long_lines.append(ln)

    # si on a des paragraphes, on prend les 1 à 4 premiers
    if long_lines:
        # évite de renvoyer un pavé énorme si la page contient trop de texte
        joined = "\n".join(long_lines[:4]).strip()
        if len(joined) >= 60:
            return joined

    # 3) Dernier fallback : premiers <p> "significatifs"
    paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    paras = [p for p in paras if p and len(p) >= 30]
    if paras:
        return "\n".join(paras[:4]).strip()

    return None


def fetch_description(detail_url: Optional[str], sleep_s: float = 0.35) -> Optional[str]:
    url = normalize_detail_url(detail_url)
    if not url:
        return None

    html = safe_get_html(url)
    if not html:
        return None

    desc = extract_description_from_html(html)

    # petit sleep pour rester "propre"
    if sleep_s and sleep_s > 0:
        time.sleep(sleep_s)

    return desc


def collect_estates_pages(
    contract_value: str,
    region: dict,
    existing_ids: set,
    max_pages: Optional[int],
) -> List[dict]:
    """
    collecte toutes les annonces via /search (pagination)
    """
    estates_all: List[dict] = []
    page = 1

    while True:
        if max_pages is not None and page > max_pages:
            print(f"[INFO] max_pages={max_pages} atteint pour {region['province_name']}")
            break

        params = {
            "section": "estate",
            "sector": "res",
            "contract": contract_value,
            "province": region["province_id"],
            "region": region["region_id"],
            "page": page,
        }

        data = safe_get_json(BASE_SEARCH_URL, params)
        if not data:
            break

        estates = data.get("estates") or []
        pagination = data.get("pagination") or {}
        current_page = pagination.get("current_page") or page
        total_pages = pagination.get("total_pages") or page

        if not estates:
            print(f"[INFO] page {page} / {total_pages} vide pour {region['province_name']}.")
            break

        print(f"page {current_page} / {total_pages} collectée ({len(estates)} annonces)")

        for est in estates:
            eid = est.get("id")
            if not eid:
                continue
            if eid in existing_ids:
                continue
            estates_all.append(est)

        if current_page >= total_pages:
            break

        page += 1
        time.sleep(1.0)

    return estates_all


def fetch_coords_map(contract_value: str, region: dict) -> Dict[int, Tuple[Optional[float], Optional[float]]]:
    """
    Appel unique à l'API carte (toutes les annonces de la zone)
    """
    map_params = {
        "contract": contract_value,
        "placeholder": region["placeholder"],
        "province": region["province_id"],
        "region": region["region_id"],
        "sector": "res",
        "type": "",
        "section": "estate",
    }

    map_data = safe_get_json(BASE_MAP_URL, map_params)
    return extract_coords_from_map(map_data or {})


# ==========================
#  Scraper principal
# ==========================

def scrape_tecnocasa(mode: str = "initial", max_pages: Optional[int] = None) -> Path:
    assert mode in {"initial", "update"}
    ensure_raw_dir()

    date_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RAW_DIR / f"tecnocasa_{mode}_{date_tag}.csv"

    existing_ids = load_existing_ids() if mode == "update" else set()
    if mode == "update":
        print(f"[INFO] Mode update : {len(existing_ids)} annonces déjà connues seront ignorées.")

    fields = [
        "listing_id",
        "title",
        "subtitle",
        "description",
        "price",
        "price_numeric",
        "previous_price",
        "surface",
        "surface_numeric",
        "rooms",
        "rooms_numeric",
        "bathrooms",
        "ad_type",
        "contract",
        "contract_slug",
        "property_type",
        "property_type_slug",
        "country",
        "province_id",
        "province_name",
        "region_id",
        "region_name",
        "city_name",
        "quarter_name",
        "detail_url",
        "image_main",
        "is_discounted",
        "discount",
        "discount_percentage",
        "exclusive",
        "top",
        "virtual_tour",
        "lat",
        "lon",
        "source",
        "scraped_at",
    ]

    total_written = 0

    with out_path.open("w", encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fields)
        writer.writeheader()

        for contract_label, contract_value in CONTRACTS.items():
            for region in REGIONS:
                print(f"\n-> Région Tecno: {region['province_name']} ({contract_label}={contract_value})")

                estates_all = collect_estates_pages(
                    contract_value=contract_value,
                    region=region,
                    existing_ids=existing_ids,
                    max_pages=max_pages,
                )
                print(f"[INFO] {len(estates_all)} annonces (nouvelles) collectées via /search.")

                if not estates_all:
                    continue

                coords_map = fetch_coords_map(contract_value=contract_value, region=region)
                print(f"[INFO] {len(coords_map)} points coords récupérés via /search-map-list.")

                for est in estates_all:
                    eid = est.get("id")
                    if not eid:
                        continue

                    coords = coords_map.get(int(eid))
                    lat, lon = coords if coords else (None, None)

                    contract_slug = (
                        est.get("contract", {}).get("slug")
                        if isinstance(est.get("contract"), dict)
                        else None
                    )
                    property_type_slug, inferred_contract_slug = parse_property_type(est.get("detail_url", ""))

                    # ✅ DESCRIPTION: on visite la page détail (HTML)
                    desc = fetch_description(est.get("detail_url"))

                    row = {
                        "listing_id": eid,
                        "title": est.get("title"),
                        "subtitle": est.get("subtitle"),
                        "description": desc,
                        "price": est.get("price"),
                        "price_numeric": normalize_price(est.get("price")),
                        "previous_price": est.get("previous_price"),
                        "surface": est.get("surface"),
                        "surface_numeric": normalize_surface(est.get("surface")),
                        "rooms": est.get("rooms"),
                        "rooms_numeric": normalize_rooms(est.get("rooms")),
                        "bathrooms": est.get("bathrooms"),
                        "ad_type": est.get("ad_type"),
                        "contract": contract_label,
                        "contract_slug": contract_slug or inferred_contract_slug,
                        "property_type": (
                            est.get("type", {}).get("title")
                            if isinstance(est.get("type"), dict)
                            else None
                        ),
                        "property_type_slug": property_type_slug,
                        "country": est.get("country"),
                        "province_id": region["province_id"],
                        "province_name": region["province_name"],
                        "region_id": region["region_id"],
                        "region_name": region["region_name"],
                        "city_name": (
                            est.get("city", {}).get("name")
                            if isinstance(est.get("city"), dict)
                            else None
                        ),
                        "quarter_name": (
                            est.get("quarter", {}).get("name")
                            if isinstance(est.get("quarter"), dict)
                            else None
                        ),
                        "detail_url": normalize_detail_url(est.get("detail_url")),
                        "image_main": (
                            (est.get("images") or [{}])[0]
                            .get("url", {})
                            .get("card")
                            if est.get("images")
                            else None
                        ),
                        "is_discounted": est.get("is_discounted"),
                        "discount": est.get("discount"),
                        "discount_percentage": est.get("discount_percentage"),
                        "exclusive": est.get("exclusive"),
                        "top": est.get("top"),
                        "virtual_tour": est.get("virtual_tour"),
                        "lat": lat,
                        "lon": lon,
                        "source": "tecnocasa",
                        "scraped_at": datetime.utcnow().isoformat(),
                    }

                    writer.writerow(row)
                    total_written += 1
                    existing_ids.add(eid)

    print(f"\n[OK] Fichier écrit : {out_path} ({total_written} lignes)")
    return out_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scraper Tecnocasa (vente + location) - CSV unique - description via HTML")
    parser.add_argument("--mode", choices=["initial", "update"], default="initial")
    parser.add_argument("--max-pages", type=int, default=None)

    args = parser.parse_args()
    scrape_tecnocasa(mode=args.mode, max_pages=args.max_pages)