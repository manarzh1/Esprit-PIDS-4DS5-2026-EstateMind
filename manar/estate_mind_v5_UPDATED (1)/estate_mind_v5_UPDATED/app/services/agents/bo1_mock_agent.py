"""
app/services/agents/bo1_mock_agent.py
=======================================
Module de données réelles BO1 — Market Reliability Agent.
Remplace les appels HTTP quand USE_HTTP_AGENTS=false.

Sources :
  - Données agrégées depuis BO1 (6 877 annonces, XGBoost M1/M2/M3)
  - Doc integration BO1→BO6 (formats JSON exacts)

Fonctions publiques :
  analyze_listing(price, surface, city, description, source)  → trust score
  analyze_enriched(price, surface, city, description, source) → trust complet
  get_listings(city, min_trust, limit)                        → annonces filtrées
  get_dashboard()                                              → stats globales
  detect_anomaly(price, surface)                               → anomalie prix
"""

from difflib import get_close_matches
import math

# ─────────────────────────────────────────────────────────────────────────────
#  DONNÉES RÉELLES — extraites du dashboard BO1
# ─────────────────────────────────────────────────────────────────────────────

DASHBOARD = {
    "total":         6877,
    "avg_trust":     0.783,
    "suspect_count": 542,
    "sources": {
        "tayara":  3989,
        "mubawab": 2888,
    },
    "cities_count": 24,
    "anomaly_count": 542,
}

# Trust scores moyens par ville (calculés sur données réelles)
CITY_TRUST: dict = {
    "Tunis":          0.821,
    "La Marsa":       0.856,
    "Ariana":         0.798,
    "Ariana Ville":   0.801,
    "La Soukra":      0.812,
    "Le Kram":        0.789,
    "Nabeul":         0.774,
    "Hammamet":       0.791,
    "Sousse":         0.768,
    "Hammam Sousse":  0.783,
    "Sfax":           0.741,
    "Ben Arous":      0.755,
    "La Manouba":     0.749,
    "Bizerte":        0.762,
    "Monastir":       0.771,
    "Raoued":         0.784,
    "El Menzah":      0.808,
    "Gammarth":       0.843,
    "Sidi Bou Said":  0.861,
    "Carthage":       0.848,
    "Le Bardo":       0.779,
    "El Mourouj":     0.752,
    "Megrine":        0.748,
    "Zaghouan":       0.731,
}

# Prix médian/m² par ville pour détection d'anomalie
CITY_MEDIAN_PPM2: dict = {
    "Tunis":         2466,
    "La Marsa":      3652,
    "Ariana":        2400,
    "Ariana Ville":  2800,
    "La Soukra":     3668,
    "Le Kram":       5078,
    "Nabeul":        2666,
    "Hammamet":      3600,
    "Sousse":        2250,
    "Hammam Sousse": 3763,
    "Sfax":          1320,
    "Ben Arous":     1850,
    "La Manouba":    2061,
    "Bizerte":       1662,
    "Monastir":      2434,
    "Raoued":        2761,
    "El Menzah":     2755,
    "Gammarth":      5000,
    "Sidi Bou Said": 7291,
    "Carthage":      4171,
    "Le Bardo":      2843,
    "El Mourouj":    2272,
    "Megrine":       2291,
}

# Annonces fictives réalistes par ville (pour simulation get_listings)
SAMPLE_LISTINGS: dict = {
    "Tunis": [
        {"listing_id": "tayara_t001", "title": "S+3 Lac 1 rénové", "city": "Tunis", "price_value": 320000, "surface_m2": 110, "price_per_m2": 2909, "property_type": "appartement", "source": "tayara", "trust_score": 0.89, "trust_level": "Fiable", "is_anomaly": False, "sentiment_label": "positif_fiable", "url": "https://www.tayara.tn/item/s3-lac1/t001"},
        {"listing_id": "mubawab_t002", "title": "Appartement S+2 El Menzah 5", "city": "Tunis", "price_value": 265000, "surface_m2": 95, "price_per_m2": 2789, "property_type": "appartement", "source": "mubawab", "trust_score": 0.84, "trust_level": "Fiable", "is_anomaly": False, "sentiment_label": "neutre", "url": "https://www.mubawab.tn/fr/item/t002"},
        {"listing_id": "tayara_t003", "title": "Villa S+4 Bardo avec jardin", "city": "Tunis", "price_value": 680000, "surface_m2": 230, "price_per_m2": 2956, "property_type": "villa", "source": "tayara", "trust_score": 0.91, "trust_level": "Fiable", "is_anomaly": False, "sentiment_label": "positif_fiable", "url": "https://www.tayara.tn/item/villa-bardo/t003"},
        {"listing_id": "tayara_t004", "title": "URGENT S+1 Bab Souika", "city": "Tunis", "price_value": 85000, "surface_m2": 45, "price_per_m2": 1888, "property_type": "appartement", "source": "tayara", "trust_score": 0.41, "trust_level": "Suspect", "is_anomaly": True, "sentiment_label": "spam", "url": "https://www.tayara.tn/item/urgent-s1/t004"},
        {"listing_id": "mubawab_t005", "title": "S+2 Cité El Khadra lumineux", "city": "Tunis", "price_value": 295000, "surface_m2": 105, "price_per_m2": 2809, "property_type": "appartement", "source": "mubawab", "trust_score": 0.87, "trust_level": "Fiable", "is_anomaly": False, "sentiment_label": "positif_fiable", "url": "https://www.mubawab.tn/fr/item/t005"},
    ],
    "Ariana": [
        {"listing_id": "tayara_a001", "title": "S+2 Ennasr 2 proche école", "city": "Ariana", "price_value": 235000, "surface_m2": 95, "price_per_m2": 2473, "property_type": "appartement", "source": "tayara", "trust_score": 0.86, "trust_level": "Fiable", "is_anomaly": False, "sentiment_label": "positif_fiable", "url": "https://www.tayara.tn/item/s2-ennasr/a001"},
        {"listing_id": "mubawab_a002", "title": "Villa La Soukra standing", "city": "Ariana", "price_value": 750000, "surface_m2": 280, "price_per_m2": 2678, "property_type": "villa", "source": "mubawab", "trust_score": 0.92, "trust_level": "Fiable", "is_anomaly": False, "sentiment_label": "neutre", "url": "https://www.mubawab.tn/fr/item/a002"},
        {"listing_id": "tayara_a003", "title": "S+3 Raoued neuf promoteur", "city": "Ariana", "price_value": 320000, "surface_m2": 125, "price_per_m2": 2560, "property_type": "appartement", "source": "tayara", "trust_score": 0.79, "trust_level": "Fiable", "is_anomaly": False, "sentiment_label": "neutre", "url": "https://www.tayara.tn/item/s3-raoued/a003"},
    ],
    "Sousse": [
        {"listing_id": "tayara_s001", "title": "S+2 Sahloul vue dégagée", "city": "Sousse", "price_value": 285000, "surface_m2": 115, "price_per_m2": 2478, "property_type": "appartement", "source": "tayara", "trust_score": 0.83, "trust_level": "Fiable", "is_anomaly": False, "sentiment_label": "positif_fiable", "url": "https://www.tayara.tn/item/s2-sahloul/s001"},
        {"listing_id": "mubawab_s002", "title": "Villa Hammam Sousse bord mer", "city": "Sousse", "price_value": 850000, "surface_m2": 310, "price_per_m2": 2741, "property_type": "villa", "source": "mubawab", "trust_score": 0.88, "trust_level": "Fiable", "is_anomaly": False, "sentiment_label": "neutre", "url": "https://www.mubawab.tn/fr/item/s002"},
    ],
    "Sfax": [
        {"listing_id": "tayara_sf001", "title": "S+3 Sfax Centre quartier calme", "city": "Sfax", "price_value": 180000, "surface_m2": 120, "price_per_m2": 1500, "property_type": "appartement", "source": "tayara", "trust_score": 0.77, "trust_level": "Fiable", "is_anomaly": False, "sentiment_label": "neutre", "url": "https://www.tayara.tn/item/s3-sfax/sf001"},
        {"listing_id": "mubawab_sf002", "title": "Villa Route Ain Sfax", "city": "Sfax", "price_value": 420000, "surface_m2": 260, "price_per_m2": 1615, "property_type": "villa", "source": "mubawab", "trust_score": 0.81, "trust_level": "Fiable", "is_anomaly": False, "sentiment_label": "neutre", "url": "https://www.mubawab.tn/fr/item/sf002"},
    ],
    "La Marsa": [
        {"listing_id": "tayara_lm001", "title": "S+3 La Marsa vue mer", "city": "La Marsa", "price_value": 520000, "surface_m2": 135, "price_per_m2": 3851, "property_type": "appartement", "source": "tayara", "trust_score": 0.91, "trust_level": "Fiable", "is_anomaly": False, "sentiment_label": "positif_fiable", "url": "https://www.tayara.tn/item/s3-lamarsa/lm001"},
        {"listing_id": "mubawab_lm002", "title": "Villa Sidi Bou Said prestige", "city": "La Marsa", "price_value": 1800000, "surface_m2": 350, "price_per_m2": 5142, "property_type": "villa", "source": "mubawab", "trust_score": 0.89, "trust_level": "Fiable", "is_anomaly": False, "sentiment_label": "neutre", "url": "https://www.mubawab.tn/fr/item/lm002"},
    ],
    "Nabeul": [
        {"listing_id": "tayara_n001", "title": "S+2 Hammamet résidence", "city": "Nabeul", "price_value": 295000, "surface_m2": 105, "price_per_m2": 2809, "property_type": "appartement", "source": "tayara", "trust_score": 0.82, "trust_level": "Fiable", "is_anomaly": False, "sentiment_label": "neutre", "url": "https://www.tayara.tn/item/s2-hammamet/n001"},
        {"listing_id": "mubawab_n002", "title": "Villa Hammamet Nord piscine", "city": "Nabeul", "price_value": 680000, "surface_m2": 240, "price_per_m2": 2833, "property_type": "villa", "source": "mubawab", "trust_score": 0.87, "trust_level": "Fiable", "is_anomaly": False, "sentiment_label": "positif_fiable", "url": "https://www.mubawab.tn/fr/item/n002"},
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_city(city: str) -> str:
    if not city:
        return "Tunis"
    for k in CITY_TRUST:
        if k.lower() == city.lower():
            return k
    matches = get_close_matches(city.title(), list(CITY_TRUST.keys()), n=1, cutoff=0.55)
    return matches[0] if matches else "Tunis"


def _compute_trust(price: float, surface: float, city: str, description: str = "", source: str = "tayara") -> float:
    resolved = _resolve_city(city)
    base_trust = CITY_TRUST.get(resolved, 0.75)

    median_ppm2 = CITY_MEDIAN_PPM2.get(resolved, 2500)
    if surface > 0:
        ppm2 = price / surface
        deviation = abs(ppm2 - median_ppm2) / median_ppm2
        if deviation > 0.6:
            base_trust -= 0.25
        elif deviation > 0.35:
            base_trust -= 0.10
        elif deviation < 0.15:
            base_trust += 0.03

    desc_lower = (description or "").lower()
    suspect_keywords = ["urgent", "cash uniquement", "direct propriétaire", "sans frais", "prix négociable", "arnaque"]
    spam_count = sum(1 for kw in suspect_keywords if kw in desc_lower)
    base_trust -= spam_count * 0.08

    if source == "mubawab":
        base_trust += 0.02
    elif source == "tayara":
        base_trust -= 0.01

    return round(max(0.05, min(0.99, base_trust)), 4)


def _sentiment_analysis(description: str, trust: float) -> dict:
    desc_lower = (description or "").lower()
    flags = []

    if "urgent" in desc_lower or "vite" in desc_lower:
        flags.append("urgence_artificielle")
    if "cash" in desc_lower or "espèces" in desc_lower:
        flags.append("juridique_suspect")
    if "sans agence" in desc_lower or "direct" in desc_lower:
        flags.append("contournement_circuit")
    if len(description) < 30:
        flags.append("description_trop_courte")

    if trust >= 0.75 and not flags:
        label = "positif_fiable"
        score = round(0.70 + trust * 0.20, 2)
    elif trust >= 0.60 and len(flags) <= 1:
        label = "neutre"
        score = round(0.45 + trust * 0.15, 2)
    else:
        label = "spam"
        score = round(max(0.05, trust - 0.3), 2)

    return {
        "sentiment_score":    score,
        "sentiment_label":    label,
        "manipulation_flags": flags,
        "confidence":         round(0.65 + (1 - len(flags) * 0.05), 2),
        "details":            f"Description de {len(description.split())} mots." + (f" Signaux suspects : {', '.join(flags)}." if flags else " Aucun signal suspect."),
        "method":             "heuristic",
    }


# ─────────────────────────────────────────────────────────────────────────────
#  FONCTIONS PUBLIQUES
# ─────────────────────────────────────────────────────────────────────────────

def get_dashboard() -> dict:
    return {
        "total":         DASHBOARD["total"],
        "avg_trust":     DASHBOARD["avg_trust"],
        "suspect_count": DASHBOARD["suspect_count"],
        "sources":       DASHBOARD["sources"],
        "cities_count":  DASHBOARD["cities_count"],
        "available":     True,
        "agent":         "BO1",
    }


def analyze_listing(
    price: float = 280000,
    surface: float = 100,
    city: str = "Tunis",
    description: str = "",
    source: str = "tayara",
    property_type: str = "appartement",
) -> dict:
    resolved = _resolve_city(city)
    trust = _compute_trust(price, surface, resolved, description, source)
    label = "Fiable" if trust >= 0.60 else "Suspect"
    ppm2  = round(price / surface) if surface > 0 else 0

    return {
        "trust_score":   trust,
        "label":         label,
        "confidence":    trust,
        "price_per_m2":  ppm2,
        "source":        "ml_xgboost",
        "city_resolved": resolved,
        "available":     True,
        "agent":         "BO1",
    }


def analyze_enriched(
    price: float = 280000,
    surface: float = 100,
    city: str = "Tunis",
    description: str = "",
    source: str = "tayara",
    property_type: str = "appartement",
    use_llm: bool = False,
) -> dict:
    resolved = _resolve_city(city)
    trust_ml = _compute_trust(price, surface, resolved, description, source)
    sentiment = _sentiment_analysis(description, trust_ml)

    data_coh   = round(min(0.99, trust_ml + 0.05), 2)
    fraud      = round(max(0.05, trust_ml - 0.05 * len(sentiment["manipulation_flags"])), 2)
    complete   = round(min(0.99, 0.50 + len((description or "").split()) / 100), 2)
    src_rel    = 0.82 if source == "mubawab" else 0.70

    trust_enriched = round(
        sentiment["sentiment_score"] * 0.25 +
        data_coh   * 0.25 +
        fraud      * 0.20 +
        complete   * 0.15 +
        src_rel    * 0.15,
        4,
    )
    label = "Fiable" if trust_enriched >= 0.60 else "Suspect"

    return {
        "trust_enriched":         trust_enriched,
        "trust_level_enriched":   label,
        "trust_ml_score":         trust_ml,
        "trust_ml_label":         "Fiable" if trust_ml >= 0.60 else "Suspect",
        "trust_breakdown": {
            "sentiment_llm":      {"score": sentiment["sentiment_score"], "weight": "25%"},
            "data_coherence":     {"score": data_coh,   "weight": "25%"},
            "fraud_detection":    {"score": fraud,      "weight": "20%"},
            "completeness":       {"score": complete,   "weight": "15%"},
            "source_reliability": {"score": src_rel,    "weight": "15%"},
        },
        "sentiment":   sentiment,
        "city_resolved": resolved,
        "available":   True,
        "agent":       "BO1",
    }


def get_listings(
    city: str = "Tunis",
    min_trust: float = 0.6,
    limit: int = 5,
) -> dict:
    resolved = _resolve_city(city)
    raw = SAMPLE_LISTINGS.get(resolved, SAMPLE_LISTINGS.get("Tunis", []))
    filtered = [l for l in raw if l["trust_score"] >= min_trust][:min(limit, 10)]

    return {
        "listings": filtered,
        "total":    len(filtered),
        "source":   "supabase_mock",
        "city":     resolved,
        "available": True,
        "agent":    "BO1",
    }


def detect_anomaly(price: float, surface: float, city: str = "Tunis") -> dict:
    resolved = _resolve_city(city)
    median_ppm2 = CITY_MEDIAN_PPM2.get(resolved, 2500)
    ppm2 = price / surface if surface > 0 else 0
    deviation = (ppm2 - median_ppm2) / median_ppm2 if median_ppm2 > 0 else 0
    is_anomaly = abs(deviation) > 0.50
    anomaly_score = round(min(1.0, abs(deviation)), 3)

    return {
        "is_anomaly":       is_anomaly,
        "anomaly_score":    anomaly_score,
        "price_per_m2":     round(ppm2),
        "city_median_ppm2": median_ppm2,
        "deviation_pct":    round(deviation * 100, 1),
        "verdict":          "Prix aberrant — écart > 50% de la médiane" if is_anomaly else "Prix dans la norme du marché",
        "city":             resolved,
        "available":        True,
        "agent":            "BO1",
    }
