import csv
import re
import time
import json
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Tuple
from pathlib import Path
from datetime import datetime

import requests
from bs4 import BeautifulSoup


# ------------- CONFIG GÉNÉRALE ------------- #

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

# Catégories à scraper (tu peux en ajouter plus tard)
CATEGORIES = {
    "vente": "https://www.mubawab.tn/fr/sc/appartements-a-vendre",
    "location": "https://www.mubawab.tn/fr/sc/appartements-a-louer",
    "vacances": "https://www.mubawab.tn/fr/sc/appartements-vacational",
}

# Pour tester sans exploser le site :
# ✅ Mets 1 ou 2 pour un test rapide, puis augmente (10, 50, None...)
MAX_PAGES_PER_CATEGORY: Optional[int] =1  # ↑ augmente après validation
DELAY_BETWEEN_REQUESTS = 1.0  # secondes

# Emplacements des fichiers (même convention que Remax / Tayara)
RAW_DIR = Path("data") / "raw"
STATE_DIR = Path("data") / "state"
STATE_PATH = STATE_DIR / "mubawab_state.json"


# ------------- OUTILS GÉNÉRAUX (horodatage & state) ------------- #

def now_stamp() -> str:
    """Horodatage standard : 20260222_235959 (même format que les autres connecteurs)."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def load_state() -> Dict:
    """Charge le fichier de state Mubawab (liste des ids déjà vus)."""
    if not STATE_PATH.exists():
        return {}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return {}
    except Exception as e:
        print(f"⚠️ Impossible de lire le state Mubawab ({STATE_PATH}): {e}")
        return {}


def save_state(state: Dict) -> None:
    """Sauvegarde le state Mubawab."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ------------- STRUCTURE DES DONNÉES ------------- #

@dataclass
class Listing:
    source: str
    category: str
    property_type: str
    listing_id: Optional[str]
    title: str
    price_text: str
    location_raw: Optional[str]
    area: Optional[str]
    city: Optional[str]
    surface_text: Optional[str]
    rooms_text: Optional[str]
    bedrooms_text: Optional[str]
    bathrooms_text: Optional[str]
    url: Optional[str]
    # --- champs issus de la page détail ---
    description: Optional[str]
    latitude: Optional[str]
    longitude: Optional[str]
    # Caractéristiques générales (bloc "Caractéristiques générales")
    type_bien: Optional[str] = None
    etat_general: Optional[str] = None
    etat_construction: Optional[str] = None
    standing: Optional[str] = None
    etage: Optional[str] = None
    livraison: Optional[str] = None
    surface_habitable: Optional[str] = None
    surface_exterieure: Optional[str] = None
    orientation: Optional[str] = None
    type_sol: Optional[str] = None
    # Icônes type Jardin / Terrasse / Clim / Sécurité...
    extra_features: Optional[str] = None  # liste joinée par "; "


# ------------- OUTILS HTTP / PARSING ------------- #

def get_soup(url: str) -> BeautifulSoup:
    """Télécharge une page et renvoie un BeautifulSoup."""
    resp = requests.get(url, headers=BASE_HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def build_page_url(base_url: str, page: int) -> str:
    """
    Mubawab utilise souvent :p:2 à la fin de l'URL.
    On essaie ce pattern pour les pages > 1.
    """
    if page <= 1:
        return base_url
    if base_url.endswith("/"):
        return base_url + f":p:{page}"
    return base_url + f":p:{page}"


def split_location(location_text: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Découpe 'Cité el Ghazela, Raoued' en (area, city)."""
    if not location_text:
        return None, None

    parts = [p.strip() for p in location_text.split(",") if p.strip()]
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    area = ", ".join(parts[:-1])
    city = parts[-1]
    return area, city


def extract_listing_id(url: Optional[str]) -> Optional[str]:
    """Extrait l'ID de l'annonce depuis l'URL : /pa/7999771/..."""
    if not url:
        return None
    m = re.search(r"/pa/(\d+)", url)
    return m.group(1) if m else None


# ------------- PARSING DES LISTINGS (PAGE DE RÉSULTATS) ------------- #

def parse_listing_card(card, category: str) -> Optional[Dict]:
    """
    Parse un bloc d'annonce sur la page de résultats.
    On utilise les classes historiques de Mubawab :
      - h2.listingTit a  → titre + lien
      - span.priceTag    → prix
      - span.listingH3   → localisation
      - div.adDetailFeature span → surface, pièces, chambres, sdb
    Si la structure change, on essaie des fallbacks plus génériques.
    """

    # Titre + URL
    title_a = card.select_one("h2.listingTit a")
    if not title_a:
        # fallback : le premier lien dans un titre
        title_a = card.select_one("h2 a, h3 a")
    if not title_a:
        return None

    title = title_a.get_text(strip=True)
    url = title_a.get("href")
    if url and url.startswith("/"):
        url = "https://www.mubawab.tn" + url

    # Prix
    price_span = card.select_one("span.priceTag")
    if not price_span:
        # parfois un autre span dans le bloc prix
        price_span = card.select_one(".price, .listingPrice, span[class*='price']")
    price_text = price_span.get_text(strip=True) if price_span else ""

    # Localisation
    loc_span = card.select_one("span.listingH3")
    if not loc_span:
        loc_span = card.select_one(".listingH3, .location, span[class*='listingH3']")
    location_raw = loc_span.get_text(strip=True) if loc_span else None
    area, city = split_location(location_raw)

    # Détails (surface, pièces, chambres, sdb)
    detail_spans = card.select("div.adDetailFeature span")
    if not detail_spans:
        # fallback : icônes/détails dans la carte
        detail_spans = card.select("ul li span, .icon-box span")

    def get_text_or_none(idx: int) -> Optional[str]:
        if 0 <= idx < len(detail_spans):
            return detail_spans[idx].get_text(strip=True)
        return None

    surface_text = get_text_or_none(0)
    rooms_text = get_text_or_none(1)
    bedrooms_text = get_text_or_none(2)
    bathrooms_text = get_text_or_none(3)

    listing_dict = {
        "category": category,
        "title": title,
        "url": url,
        "price_text": price_text,
        "location_raw": location_raw,
        "area": area,
        "city": city,
        "surface_text": surface_text,
        "rooms_text": rooms_text,
        "bedrooms_text": bedrooms_text,
        "bathrooms_text": bathrooms_text,
    }
    return listing_dict


def get_listings_from_page(soup: BeautifulSoup, category: str) -> List[Dict]:
    """Retourne une liste de dicts pour chaque carte d'annonce sur une page."""
    cards = soup.select("div.listingBox.feat, div.listingBox")
    # fallback hyper large si jamais la classe change
    if not cards:
        cards = soup.select("article, div[class*='listing'], div[class*='result']")
    listings: List[Dict] = []

    for card in cards:
        data = parse_listing_card(card, category)
        if data:
            listings.append(data)

    return listings


# ------------- PARSING DES PAGES DE DÉTAIL ------------- #

def parse_detail_page(url: str) -> Dict[str, Optional[str]]:
    """
    Récupère description + lat/lon + caractéristiques générales
    depuis la page détail Mubawab.
    """
    try:
        soup = get_soup(url)
    except Exception as e:
        print(f"   ⚠️  Erreur en ouvrant la page détail {url}: {e}")
        return {
            "description": None,
            "latitude": None,
            "longitude": None,
            "type_bien": None,
            "etat_general": None,
            "etat_construction": None,
            "standing": None,
            "etage": None,
            "livraison": None,
            "surface_habitable": None,
            "surface_exterieure": None,
            "orientation": None,
            "type_sol": None,
            "extra_features": None,
        }

    # ---------- DESCRIPTION ----------
    description = None

    # 1) anciens sélecteurs (au cas où un autre template existe)
    desc_container = soup.select_one("#listingDescription, .description, .detailsText")

    # 2) template Mubawab actuel : <div class="blockProp"><h1.searchTitle>...<p>description</p></div>
    if not desc_container:
        desc_block = None
        for block in soup.select("div.blockProp"):
            if block.select_one("h1.searchTitle"):
                desc_block = block
                break
        if not desc_block:
            # fallback : premier blockProp
            desc_block = soup.select_one("div.blockProp")

        if desc_block:
            p = desc_block.find("p")
            if p:
                desc_container = p

    if desc_container:
        # on remplace les <br> par des espaces
        description = desc_container.get_text(" ", strip=True)

    # ---------- COORDONNÉES ----------
    latitude = None
    longitude = None

    # a) div de map (avec attributs lat / lon)
    map_el = (
        soup.select_one("#mapOpen")
        or soup.select_one("#listingMap")
        or soup.select_one(".prop-map-holder")
        or soup.select_one(".map-container")
        or soup.select_one("[data-lat][data-lng]")
    )

    if map_el:
        for attr_lat in ("data-lat", "data-latitude", "lat", "latitude"):
            if map_el.get(attr_lat):
                latitude = map_el.get(attr_lat)
                break
        for attr_lng in ("data-lng", "data-longitude", "lng", "longitude", "lon"):
            if map_el.get(attr_lng):
                longitude = map_el.get(attr_lng)
                break

    # b) fallback : inputs cachés #latField / #lngField
    if not latitude:
        lat_input = soup.select_one("#latField")
        if lat_input and lat_input.get("value"):
            latitude = lat_input["value"]

    if not longitude:
        lng_input = soup.select_one("#lngField")
        if lng_input and lng_input.get("value"):
            longitude = lng_input["value"]

    # ---------- CARACTÉRISTIQUES GÉNÉRALES ----------
    type_bien = None
    standing = None
    etage = None
    livraison = None
    surface_habitable = None
    surface_exterieure = None
    orientation = None
    type_sol = None

    # certains "Etat" / "État" (général + en cours de construction)
    etat_values: List[str] = []

    extra_features_list: List[str] = []

    caract_block = soup.select_one("div.blockProp.caractBlockProp")
    if caract_block:
        # a) gros blocs "adMainFeature" (Type de bien, Etat, Etage, Surface habitable, etc.)
        for feat in caract_block.select("div.adMainFeature"):
            label_el = feat.select_one(".adMainFeatureContentLabel")
            value_el = feat.select_one(".adMainFeatureContentValue")
            if not label_el or not value_el:
                continue

            raw_label = label_el.get_text(strip=True).rstrip(":")
            label = raw_label.lower()
            value = value_el.get_text(strip=True)

            norm_label = (
                label.replace("é", "e")
                     .replace("è", "e")
                     .replace("ê", "e")
                     .strip()
            )

            if "type de bien" in norm_label:
                type_bien = value
            elif "surface habitable" in norm_label:
                surface_habitable = value
            elif "surface exterieure" in norm_label:
                surface_exterieure = value
            elif "orientation" in norm_label:
                orientation = value
            elif "type du sol" in norm_label:
                type_sol = value
            elif "etage du bien" in norm_label:
                etage = value
            elif "standing" in norm_label:
                standing = value
            elif "livraison" in norm_label:
                livraison = value
            elif "etat" in norm_label:
                etat_values.append(value)

        # b) petites icônes (Jardin, Terrasse, Climatisation, Sécurité, etc.)
        for af in caract_block.select("div.adFeature"):
            txt = af.get_text(" ", strip=True)
            if txt:
                extra_features_list.append(txt)

    etat_general = etat_values[0] if len(etat_values) >= 1 else None
    etat_construction = etat_values[1] if len(etat_values) >= 2 else None

    # on dedup les features en gardant l'ordre
    if extra_features_list:
        # dict.fromkeys garde l'ordre des premiers éléments
        extra_features = "; ".join(dict.fromkeys(extra_features_list))
    else:
        extra_features = None

    return {
        "description": description,
        "latitude": latitude,
        "longitude": longitude,
        "type_bien": type_bien,
        "etat_general": etat_general,
        "etat_construction": etat_construction,
        "standing": standing,
        "etage": etage,
        "livraison": livraison,
        "surface_habitable": surface_habitable,
        "surface_exterieure": surface_exterieure,
        "orientation": orientation,
        "type_sol": type_sol,
        "extra_features": extra_features,
    }


# ------------- PIPELINE COMPLET ------------- #

def scrape_category(category: str, base_url: str) -> List[Listing]:
    print(f"\n==============================")
    print(f"📂 Catégorie : {category} → {base_url}")
    print(f"==============================")

    all_listings: List[Listing] = []

    # 🔁 Nouvelle logique de pagination : on boucle jusqu'à MAX_PAGES_PER_CATEGORY
    # et on s'arrête dès qu'une page ne renvoie plus d'annonces.
    max_pages = MAX_PAGES_PER_CATEGORY if MAX_PAGES_PER_CATEGORY is not None else 9999

    for page in range(1, max_pages + 1):
        page_url = build_page_url(base_url, page)
        print(f"\n🔄 Page {page} → {page_url}")

        try:
            soup = get_soup(page_url)
        except Exception as e:
            print(f"   ⚠️  Erreur en récupérant la page {page_url}: {e}")
            break

        page_listings = get_listings_from_page(soup, category)
        print(f"   ➕ {len(page_listings)} annonces trouvées sur cette page.")

        # 🛑 Si aucune annonce : fin de cette catégorie
        if not page_listings:
            print("   ❌ Aucune annonce trouvée, fin de cette catégorie.")
            break

        for i, data in enumerate(page_listings, start=1):
            url = data["url"]
            listing_id = extract_listing_id(url)

            print(f"   • Détail annonce {i}/{len(page_listings)} (id={listing_id})")

            # Détail page (description + lat/lon + caractéristiques)
            time.sleep(DELAY_BETWEEN_REQUESTS)
            if url:
                detail = parse_detail_page(url)
            else:
                detail = {
                    "description": None,
                    "latitude": None,
                    "longitude": None,
                    "type_bien": None,
                    "etat_general": None,
                    "etat_construction": None,
                    "standing": None,
                    "etage": None,
                    "livraison": None,
                    "surface_habitable": None,
                    "surface_exterieure": None,
                    "orientation": None,
                    "type_sol": None,
                    "extra_features": None,
                }

            listing = Listing(
                source="mubawab",
                category=category,
                property_type="appartement",  # lié à l'URL, tu pourras le rendre dynamique plus tard
                listing_id=listing_id,
                title=data["title"],
                price_text=data["price_text"],
                location_raw=data["location_raw"],
                area=data["area"],
                city=data["city"],
                surface_text=data["surface_text"],
                rooms_text=data["rooms_text"],
                bedrooms_text=data["bedrooms_text"],
                bathrooms_text=data["bathrooms_text"],
                url=url,
                description=detail.get("description"),
                latitude=detail.get("latitude"),
                longitude=detail.get("longitude"),
                type_bien=detail.get("type_bien"),
                etat_general=detail.get("etat_general"),
                etat_construction=detail.get("etat_construction"),
                standing=detail.get("standing"),
                etage=detail.get("etage"),
                livraison=detail.get("livraison"),
                surface_habitable=detail.get("surface_habitable"),
                surface_exterieure=detail.get("surface_exterieure"),
                orientation=detail.get("orientation"),
                type_sol=detail.get("type_sol"),
                extra_features=detail.get("extra_features"),
            )
            all_listings.append(listing)

    print(f"\n✅ Total pour {category} : {len(all_listings)} annonces collectées.")
    return all_listings


def save_to_csv(listings: List[Listing], out_path: str) -> None:
    if not listings:
        print("⚠️  Aucune annonce à sauvegarder.")
        return

    fieldnames = list(asdict(listings[0]).keys())
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for listing in listings:
            writer.writerow(asdict(listing))

    print(f"\n✅ {len(listings)} annonces sauvegardées dans : {out_path}")


# ------------- FONCTIONS INITIAL / UPDATE ------------- #

def run_initial(max_pages: Optional[int] = None) -> Path:
    """
    Scraping INITIAL :
    - parcourt les catégories définies dans CATEGORIES
    - écrit un CSV horodaté dans data/raw/mubawab_initial_YYYYMMDD_HHMMSS.csv
    - met à jour le state avec tous les listing_id vus
    """
    global MAX_PAGES_PER_CATEGORY

    prev_max = MAX_PAGES_PER_CATEGORY
    if max_pages is not None:
        MAX_PAGES_PER_CATEGORY = max_pages

    all_listings: List[Listing] = []

    for category, url in CATEGORIES.items():
        try:
            listings_cat = scrape_category(category, url)
            all_listings.extend(listings_cat)
        except Exception as e:
            print(f"❌ Erreur pour la catégorie {category}: {e}")

    # on restaure la config globale
    MAX_PAGES_PER_CATEGORY = prev_max

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ts = now_stamp()
    out_path = RAW_DIR / f"mubawab_initial_{ts}.csv"
    save_to_csv(all_listings, str(out_path))

    # met à jour le state avec tous les ids rencontrés
    seen_ids = sorted({l.listing_id for l in all_listings if l.listing_id})
    save_state(
        {
            "seen_ids": seen_ids,
            "last_mode": "initial",
            "last_run": ts,
        }
    )

    return out_path


def run_update(max_pages: Optional[int] = None) -> Optional[Path]:
    """
    Scraping UPDATE :
    - recharge le state (ids déjà vus)
    - scrape à nouveau les catégories
    - ne garde que les annonces avec listing_id nouveau
    - écrit un CSV horodaté dans data/raw/mubawab_update_YYYYMMDD_HHMMSS.csv
    - met à jour le state avec la nouvelle union des ids
    """
    global MAX_PAGES_PER_CATEGORY

    state = load_state()
    seen_ids = set(state.get("seen_ids", []))

    prev_max = MAX_PAGES_PER_CATEGORY
    if max_pages is not None:
        MAX_PAGES_PER_CATEGORY = max_pages

    new_listings: List[Listing] = []

    for category, url in CATEGORIES.items():
        try:
            listings_cat = scrape_category(category, url)
        except Exception as e:
            print(f"❌ Erreur pour la catégorie {category}: {e}")
            continue

        for listing in listings_cat:
            lid = listing.listing_id
            if lid and lid in seen_ids:
                # déjà vu → on ignore
                continue
            # nouveaux (ou sans id) → on les garde
            new_listings.append(listing)
            if lid:
                seen_ids.add(lid)

    # on restaure la config globale
    MAX_PAGES_PER_CATEGORY = prev_max

    if not new_listings:
        print("ℹ️ UPDATE : aucun nouveau listing trouvé (tout est déjà dans le state).")
        return None

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ts = now_stamp()
    out_path = RAW_DIR / f"mubawab_update_{ts}.csv"
    save_to_csv(new_listings, str(out_path))

    # on met à jour le state
    save_state(
        {
            "seen_ids": sorted(seen_ids),
            "last_mode": "update",
            "last_run": ts,
        }
    )

    return out_path


# ------------- MAIN (pour usage direct) ------------- #

def main(mode: str = "initial") -> None:
    """
    Petit wrapper pour un lancement direct en Python.
    Par défaut, lance un scraping initial.
    """
    if mode == "initial":
        out = run_initial()
        print(f"✅ Scraping initial terminé → {out}")
    else:
        out = run_update()
        if out is None:
            print("ℹ️ Scraping update terminé : aucun nouveau bien.")
        else:
            print(f"✅ Scraping update terminé → {out}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scraper Mubawab (initial / update)")
    parser.add_argument(
        "--mode",
        choices=["initial", "update"],
        default="initial",
        help="Type de scraping à lancer.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Nombre max de pages par catégorie (override MAX_PAGES_PER_CATEGORY).",
    )

    args = parser.parse_args()

    if args.mode == "initial":
        run_initial(max_pages=args.max_pages)
    else:
        run_update(max_pages=args.max_pages)