import json
from pathlib import Path
from datetime import datetime
import time
import argparse

import requests
import pandas as pd

# ==========================
#  Config générale
# ==========================

SEARCH_URL = "https://www.remax.com.tn/search/listing-search/docs/search"

PAGE_SIZE = 24          # "top" = 24 dans le payload
MAX_PAGES_DEFAULT = 200

RAW_DIR = Path("data") / "raw"
STATE_DIR = Path("data") / "state"
STATE_PATH = STATE_DIR / "remax_state.json"

# ⚠️ Payload récupéré dans DevTools (onglet Network → Request Payload)
BASE_PAYLOAD = {
    "count": True,
    "skip": 0,      # sera écrasé dynamiquement
    "top": PAGE_SIZE,
    "searchMode": "any",
    "queryType": "full",
    "scoringProfile": "",
    "search": "*",
    "searchFields": "*",
    "filter": (
        "content/TenantId eq 6 and "
        "content/MacroRegionId eq 1048 and "
        "content/OnHoldListing eq false and "
        "content/IsRegionalOffice eq false and "
        "content/IsViewable eq true and "
        "content/OnHoldListing eq false and "
        "content/IsRegionalOffice eq false and "
        "content/IsViewable eq true"
    ),
    "minimumCoverage": 0,
    "orderby": "content/LastUpdatedOnWeb desc",
    "facets": [
        "content/RegionalZone,count:500,sort:count"
    ],
}

# Headers "navigateur" classiques
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=utf-8",
    "Origin": "https://www.remax.com.tn",
    "Referer": "https://www.remax.com.tn/listings?ListingClass=-1&TransactionTypeUID=-1",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
    # Si un jour tu prends un 403, tu peux ajouter ici un header "Cookie"
    # avec la valeur copiée depuis ton navigateur.
    # "Cookie": "copie/colle ton cookie ici"
}


# ==========================
#  Fonctions utilitaires
# ==========================

def call_search_page(skip: int) -> dict:
    """Appelle l'API Remax pour une page (paramètre skip)."""
    payload = dict(BASE_PAYLOAD)
    payload["skip"] = skip

    resp = requests.post(SEARCH_URL, json=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def pick_french_description(content: dict) -> str | None:
    """Récupère une description FR si dispo."""
    descs = content.get("ListingDescriptions") or []
    for d in descs:
        if d.get("LanguageCode") == "fr-TN":
            return d.get("Description")
    return None


def flatten_listing(item: dict) -> dict:
    """
    Transforme un enregistrement brut (item) en ligne "plate" pour le CSV.
    """
    content = item.get("content", {}) or {}

    # Coordonnées
    loc = content.get("Location") or {}
    coords = loc.get("coordinates") or [None, None]
    # Dans la réponse, c'est généralement [longitude, latitude]
    longitude = coords[0] if len(coords) > 0 else None
    latitude = coords[1] if len(coords) > 1 else None

    row = {
        # Identifiants
        "ListingKey": content.get("ListingKey"),
        "ListingId": content.get("ListingId"),

        # Info pays / région
        "ListingCountryCode": content.get("ListingCountryCode"),
        "CountryId": content.get("CountryID"),
        "RegionalZone": content.get("RegionalZone"),
        "Province": content.get("Province"),
        "City": content.get("City"),
        "LocalZone": content.get("LocalZone"),
        "PostalCode": content.get("PostalCode"),

        # Adresse
        "FullAddress": content.get("FullAddress"),
        "TitleAddress": content.get("TitleAddress"),

        # Coordonnées géographiques
        "Latitude": latitude or 0.0,
        "Longitude": longitude or 0.0,

        # Transaction / type de bien
        "ListingClass": content.get("ListingClass"),
        "TransactionTypeUID": content.get("TransactionTypeUID"),
        "PropertyTypeUID": content.get("PropertyTypeUID"),
        "CommPropertyType": content.get("CommPropertyType"),

        # Prix
        "ListingCurrency": content.get("ListingCurrency"),
        "ListingPrice": content.get("ListingPrice"),
        "ListingPriceEuro": content.get("ListingPriceEuro"),
        "RentalPriceGranularityUID": content.get("RentalPriceGranularityUID"),

        # Surfaces & pièces
        "TotalNumOfRooms": content.get("TotalNumOfRooms"),
        "NumberOfBedrooms": content.get("NumberOfBedrooms"),
        "NumberOfBathrooms": content.get("NumberOfBathrooms"),
        "TotalArea": content.get("TotalArea"),
        "LivingArea": content.get("LivingArea"),
        "LotSize": content.get("LotSize"),
        "LotSize2": content.get("LotSize2"),
        "BuiltArea": content.get("BuiltArea"),
        "ParkingSpaces": content.get("ParkingSpaces"),

        # Dates
        "FirstUpdatedToWeb": content.get("FirstUpdatedToWeb"),
        "LastUpdatedOnWeb": content.get("LastUpdatedOnWeb"),
        "OrigListingDate": content.get("OrigListingDate"),
        "ExpiryDate": content.get("ExpiryDate"),

        # Statuts internes
        "MarketStatusUID": content.get("MarketStatusUID"),
        "ListingStatusUID": content.get("ListingStatusUID"),

        # Description textuelle FR
        "Description_fr": pick_french_description(content),
    }

    return row


def load_state() -> dict:
    """Charge le state (dernier LastUpdatedOnWeb vu)."""
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state: dict) -> None:
    """Sauvegarde le state."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ==========================
#  Modes de collecte
# ==========================

def run_initial(max_pages: int, sleep_s: float) -> None:
    """
    Mode INITIAL : on récupère tout, on écrase le state.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    all_rows: list[dict] = []
    total_expected = None

    skip = 0
    page = 1

    while page <= max_pages:
        print(f"📄 [INITIAL] Page {page}/{max_pages} (skip={skip})")

        data = call_search_page(skip)

        if total_expected is None:
            total_expected = data.get("@odata.count")
            if total_expected is not None:
                print(f"   → Total annoncé par l'API : {total_expected}")

        values = data.get("value") or []
        rows = [flatten_listing(item) for item in values]
        print(f"   → {len(rows)} annonces sur cette page")

        if not rows:
            break

        all_rows.extend(rows)

        if total_expected is not None and len(all_rows) >= total_expected:
            break

        page += 1
        skip += PAGE_SIZE

        if sleep_s > 0:
            time.sleep(sleep_s)

    print(f"\n✅ Total collecté (avant déduplication) : {len(all_rows)} annonces")

    if not all_rows:
        print("Aucune annonce collectée, rien à écrire.")
        return

    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates(subset=["ListingKey"])

    # Mise à jour du state : dernier LastUpdatedOnWeb
    last_seen = (
        df["LastUpdatedOnWeb"]
        .dropna()
        .astype(str)
        .max()
    )
    save_state({"last_seen_lastupdated": last_seen})

    csv_path = RAW_DIR / f"remax_initial_{timestamp}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print(f"💾 CSV écrit dans : {csv_path.as_posix()}")
    print(f"🧠 State mis à jour : last_seen_lastupdated = {last_seen}")
    print("✨ Fini (mode initial) !")


def run_update(max_pages: int, sleep_s: float, seen_streak_stop: int) -> None:
    """
    Mode UPDATE : ne garde que les annonces plus récentes que le state.
    On s'arrête après 'seen_streak_stop' pages consécutives sans nouvelles annonces.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    state = load_state()
    last_seen = state.get("last_seen_lastupdated")

    if not last_seen:
        print("⚠️ Aucun 'last_seen_lastupdated' trouvé dans le state.")
        print("   → On se comporte comme un INITIAL allégé.")
        return run_initial(max_pages=max_pages, sleep_s=sleep_s)

    print(f"🧠 Mode UPDATE, last_seen_lastupdated = {last_seen}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    all_rows: list[dict] = []

    skip = 0
    page = 1
    pages_only_old = 0

    while page <= max_pages:
        print(f"📄 [UPDATE] Page {page}/{max_pages} (skip={skip})")

        data = call_search_page(skip)
        values = data.get("value") or []

        new_rows_page: list[dict] = []
        for item in values:
            row = flatten_listing(item)
            lu = str(row.get("LastUpdatedOnWeb") or "")

            # On garde seulement les annonces plus récentes que last_seen
            if lu and lu > last_seen:
                new_rows_page.append(row)

        print(f"   → {len(new_rows_page)} nouvelles annonces sur cette page")

        if not values:
            # plus de résultats du tout
            break

        if new_rows_page:
            pages_only_old = 0
            all_rows.extend(new_rows_page)
        else:
            pages_only_old += 1
            if pages_only_old >= seen_streak_stop:
                print(f"   → {seen_streak_stop} pages d'affilée sans nouvelles annonces, on arrête.")
                break

        page += 1
        skip += PAGE_SIZE

        if sleep_s > 0:
            time.sleep(sleep_s)

    print(f"\n✅ Total NOUVELLES annonces collectées : {len(all_rows)}")

    if not all_rows:
        print("Aucune nouvelle annonce, pas de CSV créé.")
        return

    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates(subset=["ListingKey"])

    # Met à jour le state avec la date max du nouveau batch
    last_seen_new = (
        df["LastUpdatedOnWeb"]
        .dropna()
        .astype(str)
        .max()
    )
    if last_seen_new and last_seen_new > last_seen:
        save_state({"last_seen_lastupdated": last_seen_new})
        print(f"🧠 State mis à jour : last_seen_lastupdated = {last_seen_new}")
    else:
        print("🧠 State inchangé (aucune date plus récente trouvée).")

    csv_path = RAW_DIR / f"remax_update_{timestamp}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print(f"💾 CSV écrit dans : {csv_path.as_posix()}")
    print("✨ Fini (mode update) !")


# ==========================
#  Entrée principale
# ==========================

def main():
    parser = argparse.ArgumentParser(description="Scraper Remax via l'API de search.")
    parser.add_argument(
        "--mode",
        choices=["initial", "update"],
        required=True,
        help="Mode de collecte : initial (dump complet) ou update (nouvelles annonces seulement).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=MAX_PAGES_DEFAULT,
        help="Nombre maximum de pages à parcourir.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.3,
        help="Temps de pause (en secondes) entre deux pages.",
    )
    parser.add_argument(
        "--seen-streak-stop",
        type=int,
        default=3,
        help="En mode update : nombre de pages consécutives sans nouveautés avant d'arrêter.",
    )

    args = parser.parse_args()

    if args.mode == "initial":
        run_initial(max_pages=args.max_pages, sleep_s=args.sleep)
    else:
        run_update(
            max_pages=args.max_pages,
            sleep_s=args.sleep,
            seen_streak_stop=args.seen_streak_stop,
        )


if __name__ == "__main__":
    main()