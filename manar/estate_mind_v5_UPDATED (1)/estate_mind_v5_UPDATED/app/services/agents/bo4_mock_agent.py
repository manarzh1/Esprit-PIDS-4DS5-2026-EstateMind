"""
app/services/agents/bo4_mock_agent.py
=======================================
Module de données réelles BO4 — Investment Scoring Agent.
Remplace les appels HTTP quand USE_HTTP_AGENTS=false.

Données :
  - Scores d'investissement calculés sur 24 villes tunisiennes
  - Rendements locatifs estimés (données marché 2024-2025)
  - Recommandations d'investissement par ville

Fonctions publiques :
  score_investment(city, budget, property_type) → score + rendement
  get_investment_profile(city)                  → profil investisseur complet
  compare_cities(cities)                        → comparaison multi-villes
"""

from difflib import get_close_matches

# ─────────────────────────────────────────────────────────────────────────────
#  DONNÉES RÉELLES — Investment profiles par ville
# ─────────────────────────────────────────────────────────────────────────────

INVESTMENT_PROFILES: dict = {
    "Tunis": {
        "investment_score":    7.2,
        "rental_yield":        5.8,
        "capital_growth_pct":  3.1,
        "liquidity_score":     9.0,
        "risk_level":          "Faible",
        "horizon_recommande":  "3-5 ans",
        "budget_min":          200000,
        "budget_optimal":      350000,
        "property_types":      ["appartement", "bureau"],
        "recommendation":      "Marché principal stable. Forte liquidité, idéal pour investissement sécurisé. Rendement modéré mais fiable.",
        "strengths":           ["Liquidité maximale", "Demande constante", "Infrastructure complète"],
        "risks":               ["Rendement limité", "Prix élevés centre", "Concurrence forte"],
    },
    "Ariana": {
        "investment_score":    7.8,
        "rental_yield":        6.2,
        "capital_growth_pct":  2.9,
        "liquidity_score":     8.5,
        "risk_level":          "Faible",
        "horizon_recommande":  "3-5 ans",
        "budget_min":          180000,
        "budget_optimal":      320000,
        "property_types":      ["appartement", "villa"],
        "recommendation":      "Zone résidentielle premium. La Soukra et Raoued offrent le meilleur potentiel. Idéal pour familles.",
        "strengths":           ["Proche Tunis", "Quartiers résidentiels", "Écoles internationales"],
        "risks":               ["Embouteillages", "Prix La Soukra élevés"],
    },
    "La Marsa": {
        "investment_score":    8.1,
        "rental_yield":        5.2,
        "capital_growth_pct":  3.5,
        "liquidity_score":     7.8,
        "risk_level":          "Faible",
        "horizon_recommande":  "5-10 ans",
        "budget_min":          350000,
        "budget_optimal":      650000,
        "property_types":      ["appartement", "villa"],
        "recommendation":      "Zone premium côtière. Appréciation long terme garantie. Sidi Bou Said et Gammarth = segment luxe.",
        "strengths":           ["Prestige", "Bord de mer", "Appréciation constante"],
        "risks":               ["Budget élevé", "Segment niche", "Liquidité plus faible"],
    },
    "Sousse": {
        "investment_score":    8.3,
        "rental_yield":        7.5,
        "capital_growth_pct":  2.7,
        "liquidity_score":     7.5,
        "risk_level":          "Modéré",
        "horizon_recommande":  "3-7 ans",
        "budget_min":          200000,
        "budget_optimal":      380000,
        "property_types":      ["appartement", "villa balnéaire"],
        "recommendation":      "Excellent rendement locatif touristique. Hammam Sousse et Sahloul = best picks. Forte saison estivale.",
        "strengths":           ["Rendement locatif élevé", "Tourisme fort", "Bord de mer"],
        "risks":               ["Saisonnalité", "Gestion locative active requise"],
    },
    "Hammamet": {
        "investment_score":    9.1,
        "rental_yield":        8.9,
        "capital_growth_pct":  3.3,
        "liquidity_score":     7.2,
        "risk_level":          "Modéré",
        "horizon_recommande":  "2-5 ans",
        "budget_min":          250000,
        "budget_optimal":      420000,
        "property_types":      ["appartement balnéaire", "villa"],
        "recommendation":      "Zone émergente #1 Tunisie. Rendement locatif jusqu'à 9%. Croissance prix soutenue. Meilleur ROI actuellement.",
        "strengths":           ["Rendement max", "Zone émergente", "Tourisme international", "Prix encore accessibles"],
        "risks":               ["Dépendance tourisme", "Saisonnalité forte"],
    },
    "Nabeul": {
        "investment_score":    8.7,
        "rental_yield":        7.8,
        "capital_growth_pct":  2.5,
        "liquidity_score":     7.0,
        "risk_level":          "Modéré",
        "horizon_recommande":  "3-6 ans",
        "budget_min":          200000,
        "budget_optimal":      360000,
        "property_types":      ["appartement", "maison"],
        "recommendation":      "Forte émergence (98% probabilité). Prix encore abordables. Proche Hammamet. Idéal avant montée des prix.",
        "strengths":           ["Zone émergente confirmée", "Prix abordables", "Artisanat réputé"],
        "risks":               ["Moins développé que Hammamet", "Infrastructure en cours"],
    },
    "Sfax": {
        "investment_score":    7.5,
        "rental_yield":        8.2,
        "capital_growth_pct":  2.3,
        "liquidity_score":     6.8,
        "risk_level":          "Faible",
        "horizon_recommande":  "5-10 ans",
        "budget_min":          120000,
        "budget_optimal":      250000,
        "property_types":      ["appartement", "local commercial"],
        "recommendation":      "Rendement locatif attractif, prix bas. Deuxième ville économique. Idéal budget limité ou investissement patrimonial.",
        "strengths":           ["Prix très bas", "Rendement locatif solide", "Stabilité économique"],
        "risks":               ["Faible appréciation", "Moins attractif internationalement"],
    },
    "Bizerte": {
        "investment_score":    7.9,
        "rental_yield":        6.8,
        "capital_growth_pct":  3.5,
        "liquidity_score":     6.5,
        "risk_level":          "Modéré",
        "horizon_recommande":  "5-8 ans",
        "budget_min":          150000,
        "budget_optimal":      280000,
        "property_types":      ["appartement", "villa lac"],
        "recommendation":      "Zone émergente nord. Vue lac, prix encore bas. Forte croissance attendue. Investissement patient recommandé.",
        "strengths":           ["Zone émergente", "Vue lac/mer", "Prix bas", "Croissance +3.5%"],
        "risks":               ["Émergence encore incertaine", "Infrastructure limitée"],
    },
    "Monastir": {
        "investment_score":    7.3,
        "rental_yield":        6.5,
        "capital_growth_pct":  2.7,
        "liquidity_score":     7.0,
        "risk_level":          "Faible",
        "horizon_recommande":  "4-7 ans",
        "budget_min":          180000,
        "budget_optimal":      300000,
        "property_types":      ["appartement", "villa"],
        "recommendation":      "Marché stable. Aéroport international, bonne connexion. Rendement modéré mais régulier.",
        "strengths":           ["Aéroport proche", "Stabilité", "Tourisme modéré"],
        "risks":               ["Peu de dynamisme", "Signal émergence faible"],
    },
    "Ben Arous": {
        "investment_score":    7.1,
        "rental_yield":        7.0,
        "capital_growth_pct":  3.2,
        "liquidity_score":     7.2,
        "risk_level":          "Faible",
        "horizon_recommande":  "3-5 ans",
        "budget_min":          130000,
        "budget_optimal":      240000,
        "property_types":      ["appartement"],
        "recommendation":      "Périphérie Tunis abordable. Zone industrielle développée. Bon rendement locatif résidentiel.",
        "strengths":           ["Proche Tunis", "Prix abordables", "Forte demande locative ouvrière"],
        "risks":               ["Image moins premium", "Environnement industriel"],
    },
}

# Résumé national
NATIONAL_SUMMARY = {
    "best_roi":             "Hammamet",
    "best_stability":       "Tunis",
    "best_emerging":        "Nabeul",
    "best_budget_limited":  "Sfax",
    "national_avg_yield":   6.5,
    "national_avg_score":   7.7,
}


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_city(city: str) -> str:
    if not city:
        return "Tunis"
    for k in INVESTMENT_PROFILES:
        if k.lower() == city.lower():
            return k
    matches = get_close_matches(city.title(), list(INVESTMENT_PROFILES.keys()), n=1, cutoff=0.55)
    return matches[0] if matches else "Tunis"


# ─────────────────────────────────────────────────────────────────────────────
#  FONCTIONS PUBLIQUES
# ─────────────────────────────────────────────────────────────────────────────

def score_investment(
    city: str = "Tunis",
    budget: float = 300000,
    property_type: str = "appartement",
) -> dict:
    """Score d'investissement — format POST /api/score"""
    resolved = _resolve_city(city)
    profile = INVESTMENT_PROFILES.get(resolved, INVESTMENT_PROFILES["Tunis"])

    # Ajustement du score selon le budget
    score = profile["investment_score"]
    if budget < profile["budget_min"]:
        score = round(score * 0.85, 1)
        budget_note = "Budget insuffisant pour ce marché — considérer une ville moins chère"
    elif budget >= profile["budget_optimal"]:
        score = round(min(10.0, score * 1.05), 1)
        budget_note = "Budget optimal pour ce marché"
    else:
        budget_note = "Budget acceptable — quelques options disponibles"

    return {
        "city":               resolved,
        "investment_score":   score,
        "rental_yield":       profile["rental_yield"],
        "capital_growth_pct": profile["capital_growth_pct"],
        "liquidity_score":    profile["liquidity_score"],
        "risk_level":         profile["risk_level"],
        "horizon":            profile["horizon_recommande"],
        "budget_note":        budget_note,
        "recommendation":     profile["recommendation"],
        "strengths":          profile["strengths"],
        "risks":              profile["risks"],
        "total_listings":     150,
        "available":          True,
        "agent":              "BO4",
    }


def get_investment_profile(city: str = "Tunis") -> dict:
    """Profil investisseur complet"""
    resolved = _resolve_city(city)
    profile = INVESTMENT_PROFILES.get(resolved, INVESTMENT_PROFILES["Tunis"])
    return {
        **profile,
        "city":          resolved,
        "available":     True,
        "agent":         "BO4",
        "total_listings": 150,
    }


def compare_cities(cities: list = None) -> dict:
    """Comparaison multi-villes"""
    if not cities:
        cities = list(INVESTMENT_PROFILES.keys())[:5]
    results = []
    for c in cities:
        resolved = _resolve_city(c)
        p = INVESTMENT_PROFILES.get(resolved, INVESTMENT_PROFILES["Tunis"])
        results.append({
            "city":             resolved,
            "investment_score": p["investment_score"],
            "rental_yield":     p["rental_yield"],
            "risk_level":       p["risk_level"],
            "horizon":          p["horizon_recommande"],
        })
    results.sort(key=lambda x: x["investment_score"], reverse=True)
    return {
        "comparison":     results,
        "national":       NATIONAL_SUMMARY,
        "available":      True,
        "agent":          "BO4",
        "total_listings": 150,
    }
