"""
app/services/agents/bo2_mock_agent.py
=======================================
Module de données réelles BO2 — Territorial Dynamics Agent.
Remplace les appels HTTP quand USE_HTTP_AGENTS=false.

Sources :
  - Données Prophet + K-Means (24 villes, doc intégration BO1/BO2→BO6)
  - Format JSON exact documenté section 2.x

Fonctions publiques :
  get_forecast(city, days_ahead)      → prévision Prophet 30j
  get_clusters()                      → segmentation K-Means nationale
  get_cluster_city(city)              → segment d'une ville
  predict_emerging(city, median, vol) → probabilité émergence
  get_market_overview()               → vue synthèse nationale
  get_xai_forecast(city)              → XAI tendance + facteurs
"""

from difflib import get_close_matches

# ─────────────────────────────────────────────────────────────────────────────
#  DONNÉES RÉELLES — extraites des modèles Prophet + K-Means BO2
# ─────────────────────────────────────────────────────────────────────────────

NATIONAL_MEDIAN = 2500  # TND/m² — médiane nationale

# Prévisions Prophet par ville (mean_predicted, last_known, trend_pct, mape)
FORECAST_DATA: dict = {
    "Tunis":         {"mean_predicted": 2605, "last_known": 2520, "trend_pct": 3.1,  "mape": 12.7, "trend_label": "hausse"},
    "Ariana":        {"mean_predicted": 2665, "last_known": 2590, "trend_pct": 2.9,  "mape": 11.2, "trend_label": "hausse"},
    "La Marsa":      {"mean_predicted": 3780, "last_known": 3652, "trend_pct": 3.5,  "mape": 9.8,  "trend_label": "hausse"},
    "La Soukra":     {"mean_predicted": 3750, "last_known": 3668, "trend_pct": 2.2,  "mape": 10.5, "trend_label": "hausse"},
    "Nabeul":        {"mean_predicted": 2251, "last_known": 2666, "trend_pct": -1.2, "mape": 14.3, "trend_label": "stable"},
    "Hammamet":      {"mean_predicted": 3720, "last_known": 3600, "trend_pct": 3.3,  "mape": 13.1, "trend_label": "hausse"},
    "Sousse":        {"mean_predicted": 2310, "last_known": 2250, "trend_pct": 2.7,  "mape": 11.8, "trend_label": "hausse"},
    "Sfax":          {"mean_predicted": 1350, "last_known": 1320, "trend_pct": 2.3,  "mape": 10.2, "trend_label": "hausse"},
    "Monastir":      {"mean_predicted": 2500, "last_known": 2434, "trend_pct": 2.7,  "mape": 12.0, "trend_label": "hausse"},
    "Bizerte":       {"mean_predicted": 1720, "last_known": 1662, "trend_pct": 3.5,  "mape": 15.2, "trend_label": "hausse"},
    "Gammarth":      {"mean_predicted": 5180, "last_known": 5000, "trend_pct": 3.6,  "mape": 8.9,  "trend_label": "hausse"},
    "Sidi Bou Said": {"mean_predicted": 7500, "last_known": 7291, "trend_pct": 2.9,  "mape": 7.5,  "trend_label": "hausse"},
    "Ben Arous":     {"mean_predicted": 1910, "last_known": 1850, "trend_pct": 3.2,  "mape": 13.4, "trend_label": "hausse"},
    "Hammam Sousse": {"mean_predicted": 3870, "last_known": 3763, "trend_pct": 2.8,  "mape": 11.6, "trend_label": "hausse"},
    "Raoued":        {"mean_predicted": 2840, "last_known": 2761, "trend_pct": 2.9,  "mape": 12.2, "trend_label": "hausse"},
    "El Menzah":     {"mean_predicted": 2840, "last_known": 2755, "trend_pct": 3.1,  "mape": 10.8, "trend_label": "hausse"},
    "Le Kram":       {"mean_predicted": 5210, "last_known": 5078, "trend_pct": 2.6,  "mape": 9.4,  "trend_label": "hausse"},
    "Carthage":      {"mean_predicted": 4290, "last_known": 4171, "trend_pct": 2.9,  "mape": 8.1,  "trend_label": "hausse"},
    "Le Bardo":      {"mean_predicted": 2930, "last_known": 2843, "trend_pct": 3.1,  "mape": 11.0, "trend_label": "hausse"},
    "La Manouba":    {"mean_predicted": 2120, "last_known": 2061, "trend_pct": 2.9,  "mape": 13.7, "trend_label": "hausse"},
}

# Clusters K-Means — profils segments marché
CLUSTER_PROFILES = [
    {"cluster_id": 0, "n_cities": 5,  "avg_price_m2": 5200, "label": "Métropoles premium",    "cities": ["Sidi Bou Said", "Gammarth", "Le Kram", "Carthage", "La Marsa"]},
    {"cluster_id": 1, "n_cities": 6,  "avg_price_m2": 3400, "label": "Marchés côtiers",       "cities": ["La Soukra", "Hammam Sousse", "Hammamet", "Le Bardo", "El Menzah", "El Kram"]},
    {"cluster_id": 2, "n_cities": 7,  "avg_price_m2": 2500, "label": "Villes intermédiaires", "cities": ["Tunis", "Ariana", "Raoued", "Nabeul", "Monastir", "El Mourouj", "Sousse"]},
    {"cluster_id": 3, "n_cities": 4,  "avg_price_m2": 1800, "label": "Marchés abordables",    "cities": ["Sfax", "Bizerte", "Ben Arous", "La Manouba"]},
    {"cluster_id": 4, "n_cities": 2,  "avg_price_m2": 1200, "label": "Marchés en développement", "cities": ["Zaghouan", "Gafsa"]},
]

# Probabilités d'émergence par ville (M6)
EMERGENCE_DATA: dict = {
    "Nabeul":        {"is_emerging": True,  "proba": 0.998, "price_vs_national": 1.07, "recommandation": "Zone à surveiller activement — investissement potentiel"},
    "Mahdia":        {"is_emerging": True,  "proba": 0.870, "price_vs_national": 0.85, "recommandation": "Signal modéré — surveiller sur 6 mois"},
    "Bizerte":       {"is_emerging": True,  "proba": 0.610, "price_vs_national": 0.66, "recommandation": "Signal modéré — zone en développement"},
    "Hammamet":      {"is_emerging": True,  "proba": 0.920, "price_vs_national": 1.44, "recommandation": "Zone touristique émergente — potentiel locatif élevé"},
    "Sousse":        {"is_emerging": True,  "proba": 0.755, "price_vs_national": 0.90, "recommandation": "Marché côtier en croissance régulière"},
    "Monastir":      {"is_emerging": False, "proba": 0.420, "price_vs_national": 0.97, "recommandation": "Marché stable — peu de signal d'émergence"},
    "Sfax":          {"is_emerging": False, "proba": 0.310, "price_vs_national": 0.53, "recommandation": "Marché mature à prix bas — rendement locatif intéressant"},
    "Ariana":        {"is_emerging": True,  "proba": 0.680, "price_vs_national": 0.96, "recommandation": "Zone résidentielle en croissance — bonne liquidité"},
    "Tunis":         {"is_emerging": False, "proba": 0.490, "price_vs_national": 0.99, "recommandation": "Marché principal stable — sécurisé mais rendement modéré"},
    "La Marsa":      {"is_emerging": False, "proba": 0.280, "price_vs_national": 1.46, "recommandation": "Marché premium stabilisé — entrée de gamme haute"},
    "Gammarth":      {"is_emerging": False, "proba": 0.210, "price_vs_national": 2.00, "recommandation": "Segment luxe — investissement long terme"},
    "Ben Arous":     {"is_emerging": True,  "proba": 0.590, "price_vs_national": 0.74, "recommandation": "Périphérie en développement — bon rapport qualité/prix"},
}

# Zones recommandées par ville (pour location_analysis)
RECOMMEND_ZONES: dict = {
    "Tunis": [
        {"zone": "El Menzah",   "price": 350000, "ppm2": 2755, "score": 8.2, "avantages": ["Calme résidentiel", "Proche école", "Infrastructure complète"], "trend": 3.1},
        {"zone": "Cité El Khadra", "price": 280000, "ppm2": 3333, "score": 7.9, "avantages": ["Centre ville", "Transport", "Commerce proche"], "trend": 2.8},
        {"zone": "Le Bardo",    "price": 265000, "ppm2": 2843, "score": 7.5, "avantages": ["Accessible", "Quartier historique", "Bonne connexion"], "trend": 3.1},
    ],
    "Ariana": [
        {"zone": "La Soukra",   "price": 399500, "ppm2": 3668, "score": 8.7, "avantages": ["Prestige", "Proche aéroport", "Villas standing"], "trend": 2.2},
        {"zone": "Raoued",      "price": 348000, "ppm2": 2761, "score": 8.1, "avantages": ["Neuf promoteur", "Grand espace", "Investissement sûr"], "trend": 2.9},
        {"zone": "Ariana Ville","price": 350000, "ppm2": 2800, "score": 7.8, "avantages": ["Centre Ariana", "Tous services", "Bonne liquidité"], "trend": 2.9},
    ],
    "Sousse": [
        {"zone": "Hammam Sousse","price": 350000, "ppm2": 3763, "score": 8.8, "avantages": ["Bord de mer", "Tourisme", "Fort rendement locatif"], "trend": 2.8},
        {"zone": "Sahloul",     "price": 370000, "ppm2": 3195, "score": 8.3, "avantages": ["Résidentiel premium", "École internationale", "Calme"], "trend": 2.7},
        {"zone": "Akouda",      "price": 366000, "ppm2": 3791, "score": 7.9, "avantages": ["Vue mer", "Résidence balnéaire", "Potentiel locatif"], "trend": 2.5},
    ],
    "Sfax": [
        {"zone": "Sfax Centre", "price": 175000, "ppm2": 1500, "score": 7.1, "avantages": ["Prix attractif", "Centre économique", "Services complets"], "trend": 2.3},
        {"zone": "Route Ain",   "price": 230000, "ppm2": 1615, "score": 6.8, "avantages": ["Espace", "Calme", "Villa accessible"], "trend": 2.0},
    ],
    "Nabeul": [
        {"zone": "Hammamet",    "price": 360000, "ppm2": 3600, "score": 9.1, "avantages": ["Zone émergente #1", "Tourisme fort", "Rendement 7-9%"], "trend": 3.3},
        {"zone": "Nabeul Ville","price": 322500, "ppm2": 2666, "score": 8.2, "avantages": ["Artisanat", "Croissance stable", "Accès rapide Tunis"], "trend": 2.5},
        {"zone": "Beni Khiar",  "price": 270000, "ppm2": 2903, "score": 7.4, "avantages": ["Calme", "Prix modéré", "Nature proche"], "trend": 2.1},
    ],
    "La Marsa": [
        {"zone": "Sidi Bou Said","price": 875000, "ppm2": 7291, "score": 9.5, "avantages": ["Prestige absolu", "Vue mer", "Patrimoine UNESCO"], "trend": 2.9},
        {"zone": "Gammarth",    "price": 725000, "ppm2": 5000, "score": 9.0, "avantages": ["Luxe", "Plages privées", "Immobilier stable"], "trend": 3.6},
        {"zone": "La Marsa Plage","price": 420000, "ppm2": 3652, "score": 8.5, "avantages": ["Bord de mer", "Prestige accessible", "Fort potentiel"], "trend": 3.5},
    ],
    "Bizerte": [
        {"zone": "Bizerte Nord","price": 212500, "ppm2": 2031, "score": 7.8, "avantages": ["Zone émergente", "Vue lac", "Prix en hausse"], "trend": 3.5},
        {"zone": "Bizerte",    "price": 292500, "ppm2": 1662, "score": 7.2, "avantages": ["Abordable", "Potentiel", "Littoral"], "trend": 3.5},
    ],
    "Monastir": [
        {"zone": "Monastir",   "price": 275000, "ppm2": 2434, "score": 7.6, "avantages": ["Stable", "Aéroport proche", "Tourisme modéré"], "trend": 2.7},
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_city(city: str) -> str:
    if not city:
        return "Tunis"
    for k in FORECAST_DATA:
        if k.lower() == city.lower():
            return k
    # Also check recommend zones
    for k in RECOMMEND_ZONES:
        if k.lower() == city.lower():
            return k
    all_cities = list(FORECAST_DATA.keys()) + list(RECOMMEND_ZONES.keys())
    matches = get_close_matches(city.title(), all_cities, n=1, cutoff=0.55)
    return matches[0] if matches else "Tunis"


def _get_cluster_for_city(city: str) -> dict:
    for cluster in CLUSTER_PROFILES:
        if city in cluster["cities"]:
            return cluster
    return CLUSTER_PROFILES[2]  # default intermédiaire


# ─────────────────────────────────────────────────────────────────────────────
#  FONCTIONS PUBLIQUES
# ─────────────────────────────────────────────────────────────────────────────

def get_forecast(city: str = "Tunis", days_ahead: int = 30) -> dict:
    """Prévision Prophet — format GET /api/ml/forecast/{city}"""
    resolved = _resolve_city(city)
    data = FORECAST_DATA.get(resolved, FORECAST_DATA["Tunis"])

    # Générer des points de forecast simulés
    last = data["last_known"]
    trend_daily = (data["mean_predicted"] - last) / max(days_ahead, 1)
    forecast_pts = []
    from datetime import date, timedelta
    start = date.today()
    for i in range(min(days_ahead, 30)):
        d = start + timedelta(days=i)
        pred = round(last + trend_daily * (i + 1))
        lower = round(pred * 0.92)
        upper = round(pred * 1.08)
        forecast_pts.append({
            "date":     d.isoformat(),
            "predicted": pred,
            "lower_80":  lower,
            "upper_80":  upper,
        })

    return {
        "city":             resolved,
        "days_ahead":       days_ahead,
        "mean_predicted":   data["mean_predicted"],
        "last_known_price": data["last_known"],
        "model_mape":       data["mape"],
        "trend_pct":        data["trend_pct"],
        "trend_label":      data["trend_label"],
        "source":           "prophet_precomputed",
        "forecast":         forecast_pts,
        "available":        True,
        "agent":            "BO2",
    }


def get_clusters() -> dict:
    """Segmentation K-Means — format GET /api/ml/clusters"""
    return {
        "n_clusters":       len(CLUSTER_PROFILES),
        "national_median":  NATIONAL_MEDIAN,
        "n_cities":         24,
        "cluster_profiles": CLUSTER_PROFILES,
        "available":        True,
        "agent":            "BO2",
    }


def get_cluster_city(city: str = "Tunis") -> dict:
    """Segment d'une ville — format GET /api/ml/clusters/{city}"""
    resolved = _resolve_city(city)
    cluster = _get_cluster_for_city(resolved)
    data = FORECAST_DATA.get(resolved, {})
    return {
        "city":          resolved,
        "cluster_id":    cluster["cluster_id"],
        "cluster_label": cluster["label"],
        "cluster_avg_ppm2": cluster["avg_price_m2"],
        "city_ppm2":     data.get("last_known", NATIONAL_MEDIAN),
        "vs_national":   round(data.get("last_known", NATIONAL_MEDIAN) / NATIONAL_MEDIAN, 2),
        "cluster_cities": cluster["cities"],
        "available":     True,
        "agent":         "BO2",
    }


def predict_emerging(city: str = "Nabeul", median_price: float = 0, volume: int = 0) -> dict:
    """Probabilité émergence M6 — format POST /api/ml/emerging/predict"""
    resolved = _resolve_city(city)
    data = EMERGENCE_DATA.get(resolved, {
        "is_emerging": False, "proba": 0.35,
        "price_vs_national": 1.0,
        "recommandation": "Données insuffisantes — analyse manuelle recommandée"
    })
    return {
        "city":              resolved,
        "is_emerging":       data["is_emerging"],
        "emergence_proba":   data["proba"],
        "price_vs_national": data["price_vs_national"],
        "national_median":   NATIONAL_MEDIAN,
        "recommandation":    data["recommandation"],
        "available":         True,
        "agent":             "BO2",
    }


def get_market_overview() -> dict:
    """Vue synthèse — format GET /api/xai/market-overview"""
    top_emerging = [
        {"city": c, "proba": d["proba"],
         "verdict": "Fort signal" if d["proba"] >= 0.85 else "Signal modéré",
         "verdict_color": "green" if d["proba"] >= 0.85 else "orange"}
        for c, d in EMERGENCE_DATA.items()
        if d["is_emerging"]
    ]
    top_emerging.sort(key=lambda x: x["proba"], reverse=True)

    forecast_cities = [
        {"city": c, "avg_predicted": d["mean_predicted"],
         "trend_pct": d["trend_pct"], "trend_label": d["trend_label"]}
        for c, d in FORECAST_DATA.items()
    ]

    return {
        "national_median":        NATIONAL_MEDIAN,
        "n_cities_analyzed":      24,
        "n_forecast_available":   len(FORECAST_DATA),
        "market_segments":        CLUSTER_PROFILES,
        "top_emerging":           top_emerging[:5],
        "forecast_cities":        forecast_cities,
        "available":              True,
        "agent":                  "BO2",
    }


def get_xai_forecast(city: str = "Tunis") -> dict:
    """XAI forecast — format GET /api/xai/forecast/{city}"""
    resolved = _resolve_city(city)
    data = FORECAST_DATA.get(resolved, FORECAST_DATA["Tunis"])
    cluster = _get_cluster_for_city(resolved)
    emerg = EMERGENCE_DATA.get(resolved, {"proba": 0.5, "is_emerging": False})

    return {
        "city":             resolved,
        "trend_summary":    f"Tendance {data['trend_label']} de {data['trend_pct']}% sur 30 jours",
        "current_ppm2":     data["last_known"],
        "predicted_ppm2":   data["mean_predicted"],
        "trend_pct":        data["trend_pct"],
        "key_factors": [
            {"factor": "Cluster marché",    "value": cluster["label"],    "impact": "positif"},
            {"factor": "Demande locative",  "value": "Forte",             "impact": "positif" if data["trend_pct"] > 2 else "neutre"},
            {"factor": "Émergence zone",    "value": f"{emerg['proba']:.0%}", "impact": "positif" if emerg["is_emerging"] else "neutre"},
            {"factor": "Médiane nationale", "value": f"{NATIONAL_MEDIAN} TND/m²", "impact": "neutre"},
        ],
        "milestones": [
            {"label": "J+30", "predicted": data["mean_predicted"], "lower": round(data["mean_predicted"] * 0.92), "upper": round(data["mean_predicted"] * 1.08)},
            {"label": "J+60", "predicted": round(data["mean_predicted"] * (1 + data["trend_pct"] / 100 * 2)), "lower": round(data["mean_predicted"] * 0.88), "upper": round(data["mean_predicted"] * 1.15)},
            {"label": "J+90", "predicted": round(data["mean_predicted"] * (1 + data["trend_pct"] / 100 * 3)), "lower": round(data["mean_predicted"] * 0.85), "upper": round(data["mean_predicted"] * 1.20)},
        ],
        "model_mape":       data["mape"],
        "available":        True,
        "agent":            "BO2",
    }


def get_recommend_zones(ville: str = "Tunis", budget: float = 300000, type_bien: str = "appartement") -> dict:
    """Zones recommandées — pour call_bo2 location_analysis"""
    resolved = _resolve_city(ville)
    zones = RECOMMEND_ZONES.get(resolved, RECOMMEND_ZONES.get("Tunis", []))

    # Filtrer par budget si applicable
    if budget > 0:
        affordable = [z for z in zones if z["price"] <= budget * 1.3]
        zones = affordable if affordable else zones

    return {
        "zones":          zones[:3],
        "ville":          resolved,
        "type_bien":      type_bien,
        "data_source":    "prophet_kmeans_bo2",
        "total_listings": sum(1 for _ in zones),
        "available":      True,
        "agent":          "BO2",
    }
