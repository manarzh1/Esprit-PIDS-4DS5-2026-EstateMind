
import argparse
import csv
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed


# ============================================================
# 1) CONFIG
# ============================================================
@dataclass
class TayaraConfig:
    base_url: str = "https://www.tayara.tn"
    listing_path: str = "/en/listing/c/immobilier"
    data_route: str = "/en/listing/c/immobilier.json"

    # pagination
    page_param: str = "page"
    start_page: int = 1
    max_pages: int = 400
    sleep_sec: float = 0.3

    extra_params: Optional[Dict[str, Any]] = None

    # outputs
    out_dir: str = "data/raw"
    state_dir: str = "data/state"
    state_file: str = "tayara_checkpoint.json"

    # http robustness
    timeout_sec: int = 25
    max_retries: int = 2
    retry_sleep_sec: float = 0.7

    # detail
    scrape_detail: bool = True
    detail_sleep_sec: float = 0.15  # now small, because parallelism does most work

    # update stopping
    stop_after_seen_streak: int = 80
    stop_after_old_pages: int = 2

    # parallelism
    workers: int = 8


# ============================================================
# 2) HELPERS
# ============================================================
BUILD_ID_RE = re.compile(r'"buildId"\s*:\s*"([^"]+)"')
NEXT_DATA_RE = re.compile(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
RE_NON_ALNUM = re.compile(r'[^a-z0-9]+', re.IGNORECASE)

RE_SURFACE = re.compile(r'(\d{2,4})\s*(m²|m2|sqm)\b', re.IGNORECASE)
RE_S_TYPED = re.compile(r'\bS\s*\+?\s*(\d)\b', re.IGNORECASE)
RE_PIECES = re.compile(r'\b(\d)\s*(pi[eè]ces|pieces)\b', re.IGNORECASE)
RE_CHAMBRES = re.compile(r'\b(\d)\s*(chambres?|ch)\b', re.IGNORECASE)


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_text(x: Any) -> Optional[str]:
    if x is None:
        return None
    if not isinstance(x, str):
        x = str(x)
    x = " ".join(x.split()).strip()
    return x if x else None


def coalesce(*vals):
    for v in vals:
        if v is not None and v != "":
            return v
    return None


def deep_get(obj: Any, path: List[Any]) -> Any:
    cur = obj
    for key in path:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, list) and isinstance(key, int):
            if 0 <= key < len(cur):
                cur = cur[key]
            else:
                return None
        else:
            return None
    return cur


def slugify(text: str) -> str:
    t = safe_text(text) or ""
    t = t.lower()
    t = RE_NON_ALNUM.sub("-", t).strip("-")
    return t[:90] if len(t) > 90 else t


def join_url(base: str, maybe_path: Optional[str]) -> Optional[str]:
    if not maybe_path:
        return None
    if maybe_path.startswith("http"):
        return maybe_path
    if not maybe_path.startswith("/"):
        maybe_path = "/" + maybe_path
    return base.rstrip("/") + maybe_path


def extract_surface_m2_from_text(title: Optional[str], desc: Optional[str]) -> Optional[int]:
    blob = " ".join([title or "", desc or ""])
    m = RE_SURFACE.search(blob)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def extract_rooms_from_text(title: Optional[str], desc: Optional[str]) -> Optional[str]:
    blob = " ".join([title or "", desc or ""])
    m = RE_S_TYPED.search(blob)
    if m:
        return f"S{m.group(1)}"
    m = RE_PIECES.search(blob)
    if m:
        return f"{m.group(1)} pieces"
    m = RE_CHAMBRES.search(blob)
    if m:
        return f"{m.group(1)} chambres"
    return None


def parse_iso_to_epoch(iso_str: Optional[str]) -> Optional[int]:
    if not iso_str:
        return None
    try:
        if iso_str.endswith("Z"):
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return None


def to_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    try:
        s = str(x).strip()
        s = re.sub(r"[^\d]", "", s)
        return int(s) if s else None
    except Exception:
        return None


def get_build_id(base_url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    for path in ["/en", "/"]:
        url = base_url.rstrip("/") + path
        r = requests.get(url, headers=headers, timeout=25)
        r.raise_for_status()
        m = BUILD_ID_RE.search(r.text)
        if m:
            return m.group(1)
    raise RuntimeError("Impossible de trouver buildId (Tayara a peut-être changé).")


def build_next_data_url(cfg: TayaraConfig, build_id: str) -> str:
    base = cfg.base_url.rstrip("/")
    route = cfg.data_route.lstrip("/")
    return f"{base}/_next/data/{build_id}/{route}"


# ============================================================
# 3) STATE (checkpoint)
# ============================================================
def load_state(cfg: TayaraConfig) -> Dict[str, Any]:
    state_path = Path(cfg.state_dir) / cfg.state_file
    if not state_path.exists():
        return {"last_published_epoch": None, "known_ids": []}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {"last_published_epoch": None, "known_ids": []}


def save_state(cfg: TayaraConfig, state: Dict[str, Any]) -> None:
    state_path = Path(cfg.state_dir) / cfg.state_file
    ensure_dir(state_path.parent)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ============================================================
# 4) SCRAPER
# ============================================================
class TayaraScraper:
    ITEMS_PATHS = [
        ["pageProps", "searchedListingsAction", "newHits"],
        ["pageProps", "searchedListingsAction", "hits"],
    ]

    def __init__(self, cfg: TayaraConfig):
        self.cfg = cfg
        self.cfg.extra_params = self.cfg.extra_params or {}

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "application/json,text/plain,*/*",
                "Referer": cfg.base_url.rstrip("/") + cfg.listing_path,
            }
        )

        self.build_id = get_build_id(cfg.base_url)
        self.endpoint = build_next_data_url(cfg, self.build_id)

    # ---------- LISTING ----------
    def fetch_json(self, page: int) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
        params = dict(self.cfg.extra_params)
        params[self.cfg.page_param] = page

        last_err = None
        for attempt in range(1, self.cfg.max_retries + 2):
            try:
                r = self.session.get(self.endpoint, params=params, timeout=self.cfg.timeout_sec)
                if not r.ok:
                    return None, r.status_code
                return r.json(), r.status_code
            except Exception as e:
                last_err = e
                if attempt <= self.cfg.max_retries:
                    time.sleep(self.cfg.retry_sleep_sec)
                else:
                    raise last_err
        return None, None

    def extract_items(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        for path in self.ITEMS_PATHS:
            hits = deep_get(data, path)
            if isinstance(hits, list):
                return hits
        return []

    # ---------- DETAIL (thread-safe session per request) ----------
    def fetch_detail_next_data(self, url: str) -> Optional[Dict[str, Any]]:
        """
        IMPORTANT: on crée une session locale ici pour éviter des soucis thread-safety.
        """
        headers = {
            "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
            "Accept": "text/html,*/*",
        }

        last_err = None
        for attempt in range(1, self.cfg.max_retries + 2):
            try:
                r = requests.get(url, timeout=self.cfg.timeout_sec, headers=headers)
                if not r.ok:
                    return None
                m = NEXT_DATA_RE.search(r.text)
                if not m:
                    return None
                return json.loads(m.group(1))
            except Exception as e:
                last_err = e
                if attempt <= self.cfg.max_retries:
                    time.sleep(self.cfg.retry_sleep_sec)
                else:
                    return None
        return None

    def build_urls_from_item(self, it: Dict[str, Any], ext_id: str, title: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        base = self.cfg.base_url.rstrip("/")
        direct = coalesce(it.get("url"), it.get("permalink"), it.get("shareUrl"))
        direct_full = join_url(base, direct) if isinstance(direct, str) else None

        slug = slugify(title or "")
        guess = f"{base}/item/{slug}/{ext_id}" if slug else f"{base}/item/{ext_id}"
        return direct_full, guess

    def parse_detail_fields_ml_ready(self, next_data: Dict[str, Any]) -> Dict[str, Any]:
        page_props = deep_get(next_data, ["props", "pageProps"]) or {}
        ad = page_props.get("adDetails") or {}
        user = page_props.get("adUserData") or {}

        # adParams -> dict(label_lower -> value)
        params_list = ad.get("adParams") or []
        params: Dict[str, Any] = {}
        if isinstance(params_list, list):
            for p in params_list:
                if not isinstance(p, dict):
                    continue
                label = safe_text(p.get("label"))
                value = p.get("value")
                if label:
                    params[label.strip().lower()] = value

        def get_param(*labels: str) -> Any:
            for lab in labels:
                v = params.get(lab.lower())
                if v is not None and v != "":
                    return v
            return None

        transaction_type = safe_text(get_param("type de transaction", "transaction type"))
        surface_m2 = to_int(get_param("superficie", "surface", "area", "m²", "m2"))
        bedrooms = to_int(get_param("chambres", "bedrooms"))
        bathrooms = to_int(get_param("salles de bains", "bathrooms", "sdb", "salles de bain"))

        property_type = safe_text(get_param("type de bien", "property type", "type", "bien"))

        detail = {
            # detail metadata
            "detail_published_on": safe_text(ad.get("publishedOn")),
            "detail_published_epoch": parse_iso_to_epoch(safe_text(ad.get("publishedOn"))),
            "detail_phone": safe_text(ad.get("phone")),
            "detail_category": safe_text(ad.get("category")),
            "detail_subcategory_id": safe_text(ad.get("subCategoryId")),
            "detail_sold": ad.get("sold"),
            "detail_deleted": ad.get("deleted"),
            "detail_state": ad.get("state"),

            # publisher/user
            "detail_publisher_id": safe_text(deep_get(ad, ["publisher", "id"])),
            "detail_user_fullname": safe_text(user.get("fullname")),
            "detail_user_is_shop": user.get("isShop"),
            "detail_user_phone": safe_text(user.get("phonenumber")),
            "detail_user_email": safe_text(user.get("email")),

            # ML features
            "transaction_type": transaction_type,
            "property_type": property_type,
            "surface_m2": surface_m2,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,

            # debug
            "detail_adparams_raw": json.dumps(params, ensure_ascii=False),
        }
        return {k: v for k, v in detail.items() if v is not None}

    def normalize_item_listing(self, it: Dict[str, Any]) -> Dict[str, Any]:
        ext_id = coalesce(it.get("external_id"), it.get("id"))
        title = safe_text(it.get("title"))
        desc = safe_text(it.get("description"))
        price = it.get("price")

        location = it.get("location") or {}
        governorate = safe_text(location.get("governorate"))
        delegation = safe_text(location.get("delegation"))

        images = it.get("images") or []
        if isinstance(images, list) and len(images) > 0:
            image0 = images[0]
            images_count = len(images)
        else:
            image0 = None
            images_count = 0

        metadata = it.get("metadata") or {}
        publisher = metadata.get("publisher") or {}

        listing_published_on = safe_text(metadata.get("publishedOn"))
        listing_published_epoch = parse_iso_to_epoch(listing_published_on)

        row = {
            "source": "tayara",
            "external_id": ext_id,

            "title": title,
            "description": desc,
            "price": price,
            "city": governorate,
            "area": delegation,

            "image": image0,
            "images_count": images_count,

            "published_on": listing_published_on,
            "published_epoch": listing_published_epoch,
            "state": metadata.get("state"),
            "category_id": metadata.get("subCategory"),
            "product_type": metadata.get("producttype"),

            "publisher_name": safe_text(publisher.get("name")),
            "publisher_is_shop": publisher.get("isShop"),
            "publisher_is_approved": publisher.get("isApproved"),

            # text fallbacks
            "surface_m2_text": extract_surface_m2_from_text(title, desc),
            "rooms_text": extract_rooms_from_text(title, desc),
        }

        url_direct, url_guess = self.build_urls_from_item(it, str(ext_id), title)
        row["url_direct"] = url_direct
        row["url_guess"] = url_guess
        row["url"] = url_direct or url_guess

        return {k: v for k, v in row.items() if v is not None}

    # ---------- Parallel detail ----------
    def _fetch_detail_job(self, ext_id: str, url: str) -> Tuple[str, Dict[str, Any]]:
        nd = self.fetch_detail_next_data(url)
        if not nd:
            return ext_id, {}
        return ext_id, self.parse_detail_fields_ml_ready(nd)

    def enrich_rows_in_parallel(self, rows: List[Dict[str, Any]]) -> None:
        """
        Mutates rows: adds detail fields.
        Only for rows with url present.
        """
        jobs = []
        for r in rows:
            ext_id = r.get("external_id")
            url = r.get("url")
            if self.cfg.scrape_detail and ext_id and url:
                jobs.append((str(ext_id), str(url)))

        if not jobs:
            return

        # Parallel
        with ThreadPoolExecutor(max_workers=max(1, self.cfg.workers)) as ex:
            future_map = {ex.submit(self._fetch_detail_job, ext_id, url): ext_id for ext_id, url in jobs}
            for fut in as_completed(future_map):
                ext_id = future_map[fut]
                try:
                    _id, detail = fut.result()
                except Exception:
                    detail = {}

                # merge back into row
                if detail:
                    for r in rows:
                        if str(r.get("external_id")) == str(ext_id):
                            r.update(detail)
                            break

                # tiny sleep to be gentle even in parallel
                if self.cfg.detail_sleep_sec > 0:
                    time.sleep(self.cfg.detail_sleep_sec)

    # ---------- RUN MODES ----------
    def run_initial(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        newest_epoch_seen: Optional[int] = None
        known_ids: set = set()

        empty_in_a_row = 0

        for page in range(self.cfg.start_page, self.cfg.max_pages + 1):
            print(f"📡 [initial] Page {page} ...", end=" ")
            data, status = self.fetch_json(page)

            if status == 404:
                print("→ 404 (fin) 🛑")
                break
            if data is None:
                print(f"→ status={status} (stop) ❌")
                break

            items = self.extract_items(data)
            print(f"items={len(items)}")

            if not items:
                empty_in_a_row += 1
                if empty_in_a_row >= 2:
                    print("🛑 2 pages vides d'affilée → arrêt.")
                    break
                continue
            else:
                empty_in_a_row = 0

            page_rows: List[Dict[str, Any]] = []
            for it in items:
                base_row = self.normalize_item_listing(it)
                ext_id = base_row.get("external_id")
                if ext_id:
                    known_ids.add(str(ext_id))

                pe = base_row.get("published_epoch")
                if isinstance(pe, int):
                    newest_epoch_seen = max(newest_epoch_seen, pe) if newest_epoch_seen else pe

                page_rows.append(base_row)

            # parallel enrich for this page (keeps memory low, faster)
            if self.cfg.scrape_detail:
                self.enrich_rows_in_parallel(page_rows)

            rows.extend(page_rows)

            if self.cfg.sleep_sec > 0:
                time.sleep(self.cfg.sleep_sec)

        state = {
            "last_published_epoch": newest_epoch_seen,
            "known_ids": sorted(list(known_ids))[-200000:],
            "updated_at": datetime.now().isoformat(),
        }
        return rows, state

    def run_update(self, state: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        rows_new: List[Dict[str, Any]] = []

        last_epoch = state.get("last_published_epoch")
        known_ids = set(map(str, state.get("known_ids") or []))

        newest_epoch_seen: Optional[int] = last_epoch
        seen_streak = 0
        old_pages_in_a_row = 0

        for page in range(1, self.cfg.max_pages + 1):
            print(f"📡 [update] Page {page} ...", end=" ")
            data, status = self.fetch_json(page)

            if status == 404:
                print("→ 404 (fin) 🛑")
                break
            if data is None:
                print(f"→ status={status} (stop) ❌")
                break

            items = self.extract_items(data)
            print(f"items={len(items)}")
            if not items:
                old_pages_in_a_row += 1
                if old_pages_in_a_row >= self.cfg.stop_after_old_pages:
                    print("🛑 pages vides/anciennes → arrêt update.")
                    break
                continue

            page_all_old = True
            page_rows_new: List[Dict[str, Any]] = []

            for it in items:
                base_row = self.normalize_item_listing(it)
                ext_id = base_row.get("external_id")
                pub_epoch = base_row.get("published_epoch")

                if isinstance(pub_epoch, int) and (last_epoch is None or pub_epoch > last_epoch):
                    page_all_old = False

                if ext_id is not None and str(ext_id) in known_ids:
                    seen_streak += 1
                    continue

                seen_streak = 0
                page_rows_new.append(base_row)

                if ext_id is not None:
                    known_ids.add(str(ext_id))
                if isinstance(pub_epoch, int):
                    newest_epoch_seen = max(newest_epoch_seen, pub_epoch) if newest_epoch_seen else pub_epoch

            # enrich new rows only
            if page_rows_new and self.cfg.scrape_detail:
                self.enrich_rows_in_parallel(page_rows_new)

            rows_new.extend(page_rows_new)

            if page_all_old and last_epoch is not None:
                old_pages_in_a_row += 1
            else:
                old_pages_in_a_row = 0

            if seen_streak >= self.cfg.stop_after_seen_streak:
                print(f"🛑 seen_streak={seen_streak} → arrêt update (déjà connu).")
                break

            if old_pages_in_a_row >= self.cfg.stop_after_old_pages:
                print("🛑 pages anciennes d'affilée → arrêt update.")
                break

            if self.cfg.sleep_sec > 0:
                time.sleep(self.cfg.sleep_sec)

        state2 = {
            "last_published_epoch": newest_epoch_seen,
            "known_ids": sorted(list(known_ids))[-200000:],
            "updated_at": datetime.now().isoformat(),
        }
        return rows_new, state2


# ============================================================
# 5) OUTPUT
# ============================================================
FIXED_HEADERS = [
    "source", "external_id", "url", "url_direct", "url_guess",
    "title", "description", "price", "city", "area",
    "image", "images_count",
    "published_on", "published_epoch", "state", "category_id", "product_type",
    "publisher_name", "publisher_is_shop", "publisher_is_approved",

    # ML-ready fixed
    "transaction_type", "property_type", "surface_m2", "bedrooms", "bathrooms",

    # text fallbacks
    "surface_m2_text", "rooms_text",

    # details
    "detail_published_on", "detail_published_epoch",
    "detail_phone", "detail_user_fullname", "detail_user_is_shop",
    "detail_user_phone", "detail_user_email",
    "detail_category", "detail_subcategory_id", "detail_state",
    "detail_sold", "detail_deleted",
    "detail_publisher_id",
    "detail_adparams_raw",
]


def save_csv(rows: List[Dict[str, Any]], out_path: Path) -> None:
    ensure_dir(out_path.parent)
    if not rows:
        print("⚠️ Aucun résultat à sauvegarder.")
        return

    for r in rows:
        for h in FIXED_HEADERS:
            if h not in r:
                r[h] = None

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIXED_HEADERS)
        w.writeheader()
        w.writerows(rows)

    print(f"📁 CSV écrit: {out_path} | lignes={len(rows)} | colonnes={len(FIXED_HEADERS)}")


# ============================================================
# 6) MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["initial", "update"], default="initial")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--seen-streak", type=int, default=80)
    parser.add_argument("--old-pages", type=int, default=2)
    parser.add_argument("--detail-sleep", type=float, default=0.12)
    args = parser.parse_args()

    cfg = TayaraConfig(
        max_pages=args.max_pages,
        sleep_sec=args.sleep,
        scrape_detail=True,
        workers=args.workers,
        stop_after_seen_streak=args.seen_streak,
        stop_after_old_pages=args.old_pages,
        detail_sleep_sec=args.detail_sleep,
        extra_params={},  # mets tes filtres ici si besoin
    )

    scraper = TayaraScraper(cfg)
    state = load_state(cfg)

    if args.mode == "initial":
        rows, new_state = scraper.run_initial()
        out_csv = Path(cfg.out_dir) / f"tayara_initial_{now_stamp()}.csv"
        save_csv(rows, out_csv)
        save_state(cfg, new_state)
        print(f"✅ checkpoint saved: {Path(cfg.state_dir) / cfg.state_file}")

    else:
        rows_new, new_state = scraper.run_update(state)
        out_csv = Path(cfg.out_dir) / f"tayara_update_{now_stamp()}.csv"
        save_csv(rows_new, out_csv)
        save_state(cfg, new_state)
        print(f"✅ checkpoint updated: {Path(cfg.state_dir) / cfg.state_file}")


if __name__ == "__main__":
    main()