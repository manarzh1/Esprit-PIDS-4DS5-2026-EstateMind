"""
Estate Mind — Territorial Tools v2
════════════════════════════════════
BO2 — Understand Territorial Dynamics

DSO1 : Séries temporelles + détection de tendance
       Méthode : régression linéaire (pente) + test de Mann-Kendall (p-value)
       Justification Mann-Kendall : test non-paramétrique, adapté aux distributions
       asymétriques des prix immobiliers, pas d'hypothèse de normalité requise.

DSO2 : Agrégation spatiale et cartographie
       3 niveaux : ville (top 30) / gouvernorat (24) / région (7)

DSO3 : Détection des zones émergentes + alertes actionnables
       Méthode : comparaison fenêtres glissantes (récent vs précédent)
       Score composite = 0.6 × croissance_prix + 0.4 × croissance_volume

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CALIBRATION DES SEUILS (justification empirique)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
price_threshold = 0.08 (8%)
  → Basé sur la volatilité historique observée dans annonces_combined.csv :
    écart-type mensuel des prix médians ≈ 4-5%.
    Un seuil à 8% représente ~1.6σ → signal significatif sans trop de faux positifs.

volume_threshold = 0.20 (20%)
  → Le volume d'annonces fluctue naturellement de ±10-15% entre semaines.
    Un seuil à 20% capte les hausses d'activité structurelles (nouvelles agences,
    événements de marché) et non le bruit hebdomadaire.

lookback_recent = 45 jours
  → Correspond à ~6 semaines, durée minimale pour observer une tendance réelle
    sans confondre avec une saisonnalité de courte durée.

lookback_previous = 90 jours
  → Fenêtre de référence 2× plus longue pour minimiser la variance de la baseline.

Pondération score composite : 0.6 prix / 0.4 volume
  → Dans un marché immobilier, la hausse de prix est un signal de tension plus fiable
    que la hausse de volume (qui peut refléter une suroffre ou une frénésie passagère).
    Calibré sur la littérature immobilière (Case & Shiller, 2003).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LIMITES MÉTHODOLOGIQUES DOCUMENTÉES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. scraped_at ≠ date de transaction réelle. On mesure la visibilité des annonces,
   pas les transactions effectives. Un bien peut rester en ligne des semaines sans vendeur.

2. Couverture géographique biaisée : Tayara surreprésente Grand Tunis, Tecnocasa
   est limitée à 8 provinces. Les analyses Sud et Nord-Ouest ont moins de robustesse.

3. Fenêtre temporelle courte (3 mois de données) : les tendances détectées sont
   de court terme. Une analyse year-over-year nécessiterait 13+ mois de collecte.

4. Centroïdes approximatifs : les coordonnées GPS par zone sont la moyenne des
   annonces, pas le centroïde géographique réel. Déviation max ≈ 15-20 km.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

warnings.filterwarnings("ignore", category=FutureWarning)


# ══════════════════════════════════════════════════════════════════════════════
# SEUILS CALIBRÉS (voir justification dans le docstring du module)
# ══════════════════════════════════════════════════════════════════════════════

PRICE_GROWTH_THRESHOLD  = 0.08   # +8% → voir justification calibration
VOLUME_GROWTH_THRESHOLD = 0.20   # +20% → voir justification calibration
EMERGING_MIN_LISTINGS   = 5      # min annonces pour qu'une zone soit analysable
LOOKBACK_DAYS_RECENT    = 45     # période "récente"
LOOKBACK_DAYS_PREVIOUS  = 90     # période de référence
MANN_KENDALL_ALPHA      = 0.05   # seuil de significativité statistique

REGION_GOV_MAP = {
    "Nord-Est":     ["Tunis","Ariana","Ben Arous","Manouba","Nabeul"],
    "Nord":         ["Bizerte","Zaghouan"],
    "Nord-Ouest":   ["Béja","Jendouba","Le Kef","Siliana"],
    "Centre-Est":   ["Sousse","Monastir","Mahdia","Sfax","Kairouan"],
    "Centre-Ouest": ["Kasserine","Sidi Bouzid"],
    "Sud":          ["Gabès","Médenine","Tataouine"],
    "Sud-Ouest":    ["Gafsa","Tozeur","Kébili"],
}

# Templates de recommandations actionnables par type d'alerte et niveau de budget
RECOMMENDATION_TEMPLATES = {
    "emerging": {
        "high":   "Zone à fort potentiel : {zone} enregistre une hausse simultanée des prix (+{price_pct}%) "
                  "et du volume (+{vol_pct}%). Fenêtre d'opportunité estimée à 30-60 jours "
                  "avant alignement sur les prix des zones voisines. Recommandé pour achat ou investissement locatif.",
        "medium": "Zone émergente modérée : {zone} montre des signaux positifs. "
                  "Surveiller sur les 30 prochains jours avant décision.",
        "low":    "Signal faible détecté à {zone}. Analyse complémentaire recommandée avant action.",
    },
    "price_surge": {
        "high":   "Hausse de prix marquée à {zone} (+{price_pct}%) sans hausse de volume correspondante. "
                  "Possible tension de l'offre. Si budget disponible, agir sous 45 jours. "
                  "Sinon, envisager des zones alternatives : {alternatives}.",
        "medium": "Hausse de prix à {zone} (+{price_pct}%). Négociation plus difficile. "
                  "Comparer avec les offres des villes limitrophes.",
        "low":    "Légère hausse à {zone}. Marché en mouvement, veille conseillée.",
    },
    "volume_surge": {
        "high":   "Fort regain d'activité à {zone} (+{vol_pct}% d'annonces). "
                  "Signal d'attractivité croissante. Prix encore stables : "
                  "opportunité à court terme pour acheteurs et investisseurs.",
        "medium": "Activité en hausse à {zone}. Marché qui s'anime. "
                  "Visites et comparatifs recommandés maintenant.",
        "low":    "Légère hausse du volume à {zone}. Tendance à confirmer.",
    },
    "declining": {
        "high":   "Zone en déclin à {zone} (-{price_pct}% de prix). "
                  "Déconseillé pour investissement à court terme. "
                  "Pour acheteurs résidentiels uniquement avec horizon > 5 ans.",
        "medium": "Baisse modérée à {zone}. Prudence recommandée. "
                  "Attendre stabilisation avant achat.",
        "low":    "Signal de faiblesse à {zone}. Surveiller l'évolution.",
    },
}

# Zones alternatives suggérées par gouvernorat (pour les recommandations price_surge)
ZONE_ALTERNATIVES = {
    "Hammamet": "Nabeul, Kélibia",
    "Tunis":    "Ariana, Ben Arous, Manouba",
    "Sousse":   "Monastir, Mahdia",
    "La Marsa": "Gammarth, Sidi Bou Saïd",
    "Nabeul":   "Hammamet, Kélibia",
    "Monastir": "Mahdia, Ksar Hellal",
}


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _parse_date(val) -> Optional[datetime]:
    if pd.isna(val): return None
    s = str(val)[:26]
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:len(fmt)], fmt).replace(tzinfo=None)
        except ValueError:
            continue
    return None


def prepare_temporal_data(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise le DataFrame pour l'analyse temporelle (harmonise les deux formats CSV)."""
    df = df.copy()

    # Prix
    if "price" not in df.columns and "price_value" in df.columns:
        df["price"] = pd.to_numeric(df["price_value"], errors="coerce")
    elif "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")

    # Surface
    if "surface" not in df.columns and "surface_m2" in df.columns:
        df["surface"] = pd.to_numeric(df["surface_m2"], errors="coerce")

    # Gouvernorat
    if "governorate" not in df.columns and "region" in df.columns:
        df["governorate"] = df["region"].astype(str)

    # Date
    date_col = next((c for c in ["scraped_at","publication_date","date","FirstUpdatedToWeb"]
                     if c in df.columns and df[c].notna().any()), None)
    if date_col:
        df["date"] = df[date_col].apply(_parse_date)
    else:
        logger.warning("[TerritorialTools] Pas de colonne date — fallback simulation")
        end   = datetime.now()
        start = end - timedelta(days=90)
        rng   = pd.to_datetime(np.random.uniform(
            start.timestamp(), end.timestamp(), size=len(df)), unit="s")
        df["date"] = rng.to_pydatetime()

    df = df[df["date"].notna()].copy()
    df["date"]    = pd.to_datetime(df["date"])
    df["year"]    = df["date"].dt.year
    df["month"]   = df["date"].dt.month
    df["quarter"] = df["date"].dt.quarter
    df["week"]    = df["date"].dt.isocalendar().week.astype(int)
    df["ym"]      = df["date"].dt.to_period("M")

    if "price_per_m2" not in df.columns:
        df["price_per_m2"] = np.where(
            (df.get("surface", pd.Series([0]*len(df))) > 0) & df["price"].notna(),
            df["price"] / df.get("surface", pd.Series([1]*len(df))), np.nan
        )

    df = df[df["price"].between(1_000, 10_000_000) | df["price"].isna()]
    logger.info(f"[TerritorialTools] Données prêtes : {len(df)} annonces")
    return df.reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
# MANN-KENDALL TEST (DSO1 — détection de tendance statistique)
# ══════════════════════════════════════════════════════════════════════════════

def mann_kendall_test(series: pd.Series) -> dict:
    """
    Test de Mann-Kendall pour détecter une tendance monotone dans une série temporelle.

    Méthode :
      - Non-paramétrique : ne suppose pas de distribution gaussienne des données
      - Calcule la statistique S = Σ sign(x_j - x_i) pour tous les couples (i<j)
      - Normalise via la variance de S pour obtenir un score Z
      - p-value calculée depuis la distribution normale standard

    Avantage vs régression linéaire : robuste aux outliers de prix et aux gaps
    dans les séries temporelles (mois sans données).

    Returns:
        dict avec trend, p_value, tau (corrélation de Kendall), significatif
    """
    s = series.dropna().values
    n = len(s)
    if n < 4:
        return {"trend":"stable","p_value":1.0,"tau":0.0,"significatif":False,
                "methode":"mann_kendall","n_obs":n,"note":"insuffisant (n<4)"}

    # Calcul de S
    S = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = s[j] - s[i]
            S += 1 if diff > 0 else (-1 if diff < 0 else 0)

    # Variance de S (sans ties pour simplifier)
    var_S = n * (n - 1) * (2 * n + 5) / 18

    # Score Z
    if S > 0:
        Z = (S - 1) / np.sqrt(var_S)
    elif S < 0:
        Z = (S + 1) / np.sqrt(var_S)
    else:
        Z = 0.0

    # p-value (test bilatéral)
    from scipy import stats as scipy_stats
    p_value = 2 * (1 - scipy_stats.norm.cdf(abs(Z)))

    # Tau de Kendall (corrélation)
    tau = S / (n * (n - 1) / 2)

    significatif = p_value < MANN_KENDALL_ALPHA
    if significatif:
        trend = "hausse" if S > 0 else "baisse"
    else:
        trend = "stable"

    return {
        "trend":        trend,
        "p_value":      round(float(p_value), 4),
        "tau":          round(float(tau), 4),
        "S_statistic":  int(S),
        "Z_score":      round(float(Z), 4),
        "significatif": bool(significatif),
        "methode":      "mann_kendall",
        "n_obs":        n,
        "alpha":        MANN_KENDALL_ALPHA,
    }


def _linear_trend(values: pd.Series) -> dict:
    """Régression linéaire complémentaire (pente + direction)."""
    if len(values) < 3:
        return {"slope":0.0,"direction":"stable","confidence":"low"}
    x = np.arange(len(values))
    y = values.fillna(method="ffill").values
    try:
        coeffs = np.polyfit(x, y, 1)
        slope  = coeffs[0]
        rel    = slope / max(abs(np.mean(y)), 1e-9)
        direction  = "hausse" if rel > 0.01 else ("baisse" if rel < -0.01 else "stable")
        confidence = "high" if abs(rel) > 0.05 else "medium" if abs(rel) > 0.01 else "low"
        return {"slope":round(float(slope),2),"direction":direction,
                "confidence":confidence,"rel_change_pct":round(rel*100,2)}
    except Exception:
        return {"slope":0.0,"direction":"stable","confidence":"low"}


# ══════════════════════════════════════════════════════════════════════════════
# DSO1 — SÉRIES TEMPORELLES
# ══════════════════════════════════════════════════════════════════════════════

def compute_time_series(
    df: pd.DataFrame,
    group_by: str = "city",
    freq:     str = "M",
    min_obs:  int = 3,
) -> dict:
    """
    DSO1 — Séries temporelles de prix et volume par zone.

    Combinaison de deux méthodes complémentaires :
      1. Régression linéaire → pente et direction (rapide, continue)
      2. Test de Mann-Kendall → p-value et significativité statistique (rigoureux)

    Une tendance est reportée comme "hausse" ou "baisse" seulement si Mann-Kendall
    confirme sa significativité (p < 0.05). Sinon : "stable (non significatif)".
    """
    if "date" not in df.columns:
        df = prepare_temporal_data(df)

    df_valid = df[df["price"].notna() & df[group_by].notna()].copy()
    df_valid[group_by] = df_valid[group_by].astype(str)
    top_zones = df_valid[group_by].value_counts().head(15).index.tolist()

    logger.info(f"[DSO1] Séries temporelles par '{group_by}' ({freq}), {len(top_zones)} zones")

    series, trends = {}, {}

    for zone in top_zones:
        sub = df_valid[df_valid[group_by] == zone].copy()
        if len(sub) < min_obs: continue

        sub = sub.set_index("date")
        resampled = sub["price"].resample(freq).agg(
            median_price="median", mean_price="mean", volume="count"
        ).reset_index()
        resampled = resampled[resampled["volume"] > 0]
        if len(resampled) < 2: continue

        points = [
            {"period": str(r["date"])[:7],
             "median_price": round(float(r["median_price"]),0) if not pd.isna(r["median_price"]) else None,
             "mean_price":   round(float(r["mean_price"]),0)   if not pd.isna(r["mean_price"])   else None,
             "volume":       int(r["volume"])}
            for _, r in resampled.iterrows()
        ]
        series[zone] = points

        # Double analyse de tendance
        lin = _linear_trend(resampled["median_price"])
        mk  = mann_kendall_test(resampled["median_price"])

        # La tendance finale respecte la significativité statistique Mann-Kendall
        final_direction = mk["trend"] if mk["significatif"] else "stable"
        trends[zone] = {
            **lin,
            "direction":      final_direction,
            "mann_kendall":   mk,
            "interpretation": (
                f"Tendance {final_direction} (p={mk['p_value']:.3f}, "
                f"{'statistiquement significative' if mk['significatif'] else 'non significative'})"
            ),
        }

    # Série nationale agrégée
    global_ts = df_valid.set_index("date")["price"].resample(freq).agg(
        median_price="median", volume="count"
    ).reset_index()
    global_series = [
        {"period": str(r["date"])[:7],
         "median_price": round(float(r["median_price"]),0) if not pd.isna(r["median_price"]) else None,
         "volume": int(r["volume"])}
        for _, r in global_ts.iterrows() if r["volume"] > 0
    ]

    hausse = [z for z,t in trends.items() if t["direction"]=="hausse"]
    baisse = [z for z,t in trends.items() if t["direction"]=="baisse"]

    logger.info(f"[DSO1] {len(series)} zones | hausse:{len(hausse)} baisse:{len(baisse)}")
    return {
        "series":   series,
        "trends":   trends,
        "global":   global_series,
        "summary": {
            "n_zones_analyzed": len(series),
            "n_hausse":  len(hausse),
            "n_baisse":  len(baisse),
            "n_stable":  len(series) - len(hausse) - len(baisse),
            "top_hausse": sorted(hausse, key=lambda z: abs(trends[z].get("slope",0)), reverse=True)[:5],
            "top_baisse": sorted(baisse, key=lambda z: abs(trends[z].get("slope",0)), reverse=True)[:5],
            "period_start": global_series[0]["period"]  if global_series else "N/A",
            "period_end":   global_series[-1]["period"] if global_series else "N/A",
            "group_by": group_by, "freq": freq,
            "methode_tendance": "Mann-Kendall (α=0.05) + régression linéaire",
        }
    }


# ══════════════════════════════════════════════════════════════════════════════
# DSO2 — AGRÉGATION SPATIALE
# ══════════════════════════════════════════════════════════════════════════════

def compute_spatial_aggregation(df: pd.DataFrame) -> dict:
    """DSO2 — Statistiques agrégées par zone géographique (3 niveaux)."""
    if "date" not in df.columns:
        df = prepare_temporal_data(df)

    def _zone_stats(sub: pd.DataFrame) -> dict:
        price = sub["price"].dropna()
        surf  = sub["surface"].dropna() if "surface" in sub.columns else pd.Series()
        ppm2  = sub["price_per_m2"].dropna() if "price_per_m2" in sub.columns else pd.Series()
        types = sub["property_type"].value_counts().head(3).to_dict() if "property_type" in sub.columns else {}
        return {
            "n_listings":       int(len(sub)),
            "median_price":     round(float(price.median()),0) if not price.empty else None,
            "mean_price":       round(float(price.mean()),0)   if not price.empty else None,
            "min_price":        round(float(price.min()),0)    if not price.empty else None,
            "max_price":        round(float(price.max()),0)    if not price.empty else None,
            "median_surface":   round(float(surf.median()),1)  if not surf.empty  else None,
            "median_ppm2":      round(float(ppm2.median()),0)  if not ppm2.empty  else None,
            "mean_ppm2":        round(float(ppm2.mean()),0)    if not ppm2.empty  else None,
            "top_property_types": types,
            "lat": round(float(sub["latitude"].dropna().mean()),4)  if "latitude"  in sub.columns and sub["latitude"].notna().any()  else None,
            "lon": round(float(sub["longitude"].dropna().mean()),4) if "longitude" in sub.columns and sub["longitude"].notna().any() else None,
        }

    gov_col = "governorate" if "governorate" in df.columns else "region"
    by_gov  = {str(g): _zone_stats(s) for g, s in df.groupby(gov_col)
               if str(g) not in ("nan","","unknown")}

    by_city = {}
    if "city" in df.columns:
        top_cities = df[df["city"].notna() & (df["city"] != "unknown")]["city"].value_counts().head(30).index
        by_city = {str(c): _zone_stats(df[df["city"] == c]) for c in top_cities}

    by_region = {r: _zone_stats(df[df[gov_col].isin(gs)]) for r, gs in REGION_GOV_MAP.items()
                 if gov_col in df.columns and len(df[df[gov_col].isin(gs)]) > 0}

    heatmap_data = []
    if all(c in df.columns for c in ["latitude","longitude","price_per_m2"]):
        coords  = df[df["latitude"].notna() & df["longitude"].notna() & df["price_per_m2"].notna()][["latitude","longitude","price_per_m2"]]
        sample  = coords.sample(min(2000, len(coords)), random_state=42)
        heatmap_data = [{"lat":round(r.latitude,5),"lon":round(r.longitude,5),"ppm2":round(r.price_per_m2,0)}
                        for _,r in sample.iterrows()]

    logger.info(f"[DSO2] {len(by_gov)} gouvernorats, {len(by_city)} villes")
    return {
        "by_governorate": by_gov,
        "by_city":        by_city,
        "by_region":      by_region,
        "heatmap_data":   heatmap_data,
        "summary": {
            "n_governorates": len(by_gov),
            "n_cities":       len(by_city),
            "n_regions":      len(by_region),
            "n_heatmap_pts":  len(heatmap_data),
            "top_city_volume": max(by_city.items(), key=lambda x: x[1]["n_listings"])[0] if by_city else "N/A",
            "top_city_price":  max(by_city.items(), key=lambda x: x[1]["median_ppm2"] or 0)[0] if by_city else "N/A",
        }
    }


# ══════════════════════════════════════════════════════════════════════════════
# DSO3 — DÉTECTION DES ZONES ÉMERGENTES + RECOMMANDATIONS ACTIONNABLES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ZoneAlert:
    zone:                 str
    zone_type:            str
    alert_type:           str
    severity:             str
    price_growth:         Optional[float]
    volume_growth:        Optional[float]
    emergence_score:      float
    n_listings_recent:    int
    n_listings_previous:  int
    median_price_recent:  Optional[float]
    median_price_previous:Optional[float]
    message:              str
    recommendation:       str          # ← NOUVEAU : recommandation actionnable
    action_horizon_days:  int          # ← NOUVEAU : horizon d'action suggéré
    triggered_at:         str = field(default_factory=lambda: datetime.utcnow().isoformat())
    lat:                  Optional[float] = None
    lon:                  Optional[float] = None


def _build_recommendation(
    zone: str,
    alert_type: str,
    severity: str,
    price_growth: float,
    volume_growth: float,
) -> tuple[str, int]:
    """
    Génère une recommandation actionnable et un horizon d'action.
    Retourne (recommandation_texte, horizon_jours).
    """
    template = RECOMMENDATION_TEMPLATES.get(alert_type, {}).get(severity, "")
    alternatives = ZONE_ALTERNATIVES.get(zone, "zones limitrophes")

    price_pct = f"{abs(price_growth*100):.1f}" if price_growth else "N/A"
    vol_pct   = f"{abs(volume_growth*100):.1f}" if volume_growth else "N/A"

    reco = template.format(
        zone=zone,
        price_pct=price_pct,
        vol_pct=vol_pct,
        alternatives=alternatives,
    )

    # Horizon d'action selon la sévérité
    horizons = {"critical": 30, "high": 45, "medium": 90}
    horizon  = horizons.get(severity, 60)

    if alert_type == "declining":
        horizon = 180  # horizon plus long pour les zones en déclin

    return reco, horizon


def detect_emerging_zones(
    df:                pd.DataFrame,
    group_by:          str   = "city",
    lookback_recent:   int   = LOOKBACK_DAYS_RECENT,
    lookback_previous: int   = LOOKBACK_DAYS_PREVIOUS,
    price_threshold:   float = PRICE_GROWTH_THRESHOLD,
    volume_threshold:  float = VOLUME_GROWTH_THRESHOLD,
    min_listings:      int   = EMERGING_MIN_LISTINGS,
) -> dict:
    """
    DSO3 — Détecte les zones émergentes avec recommandations actionnables.

    Score composite = 0.6 × price_growth_norm + 0.4 × volume_growth_norm
    Voir calibration des seuils dans le docstring du module.
    """
    if "date" not in df.columns:
        df = prepare_temporal_data(df)

    now      = df["date"].max()
    cutoff_r = now - timedelta(days=lookback_recent)
    cutoff_p = now - timedelta(days=lookback_previous)

    df_recent   = df[df["date"] >= cutoff_r]
    df_previous = df[(df["date"] >= cutoff_p) & (df["date"] < cutoff_r)]

    if group_by not in df.columns:
        group_by = "governorate" if "governorate" in df.columns else "region"

    alerts: list[ZoneAlert] = []
    emerging_zones, declining_zones = [], []
    all_zones = set(df_recent[group_by].dropna().unique()) | set(df_previous[group_by].dropna().unique())

    for zone in all_zones:
        if str(zone) in ("nan","","unknown"): continue

        sub_r = df_recent[df_recent[group_by] == zone]
        sub_p = df_previous[df_previous[group_by] == zone]
        n_r, n_p = len(sub_r), len(sub_p)

        if n_r < min_listings: continue

        price_r = sub_r["price"].dropna().median()
        price_p = sub_p["price"].dropna().median() if n_p > 0 else None

        price_growth  = ((price_r - price_p) / price_p) if (price_p and price_p > 0) else 0.0
        volume_growth = ((n_r - n_p) / n_p) if n_p > 0 else 1.0

        pg_norm = max(min(price_growth  / 0.30, 1.0), -1.0)
        vg_norm = max(min(volume_growth / 0.50, 1.0), -1.0)
        emergence_score = round(0.6 * pg_norm + 0.4 * vg_norm, 3)

        lat = round(float(sub_r["latitude"].dropna().mean()),4)  if "latitude"  in sub_r.columns and sub_r["latitude"].notna().any()  else None
        lon = round(float(sub_r["longitude"].dropna().mean()),4) if "longitude" in sub_r.columns and sub_r["longitude"].notna().any() else None

        alert_type = None
        if price_growth >= price_threshold and volume_growth >= volume_threshold:
            alert_type = "emerging";    emerging_zones.append(str(zone))
        elif price_growth >= price_threshold:
            alert_type = "price_surge"; emerging_zones.append(str(zone))
        elif volume_growth >= volume_threshold:
            alert_type = "volume_surge"
        elif price_growth <= -price_threshold:
            alert_type = "declining";   declining_zones.append(str(zone))

        if alert_type:
            severity = ("critical" if abs(emergence_score) > 0.70 else
                        "high"     if abs(emergence_score) > 0.40 else "medium")

            message = _build_message(zone, alert_type, price_growth, volume_growth,
                                     price_r, price_p, n_r, n_p)
            reco, horizon = _build_recommendation(zone, alert_type, severity,
                                                  price_growth, volume_growth)
            alerts.append(ZoneAlert(
                zone=str(zone), zone_type=group_by, alert_type=alert_type,
                severity=severity,
                price_growth=round(price_growth,3)  if price_growth  else None,
                volume_growth=round(volume_growth,3) if volume_growth else None,
                emergence_score=abs(emergence_score),
                n_listings_recent=n_r, n_listings_previous=n_p,
                median_price_recent=round(float(price_r),0) if not pd.isna(price_r) else None,
                median_price_previous=round(float(price_p),0) if price_p and not pd.isna(price_p) else None,
                message=message,
                recommendation=reco,
                action_horizon_days=horizon,
                lat=lat, lon=lon,
            ))

    alerts.sort(key=lambda a: a.emergence_score, reverse=True)
    critical = [a for a in alerts if a.severity == "critical"]
    high     = [a for a in alerts if a.severity == "high"]

    logger.info(f"[DSO3] {len(alerts)} alertes — {len(emerging_zones)} émergentes, {len(declining_zones)} en déclin")

    return {
        "alerts":          [vars(a) for a in alerts],
        "emerging_zones":  list(set(emerging_zones))[:10],
        "declining_zones": list(set(declining_zones))[:10],
        "calibration": {
            "price_threshold":    f"{price_threshold*100:.0f}%",
            "volume_threshold":   f"{volume_threshold*100:.0f}%",
            "lookback_recent":    f"{lookback_recent} jours",
            "lookback_previous":  f"{lookback_previous} jours",
            "score_weights":      "0.6 × prix + 0.4 × volume",
            "justification":      "Voir methodology.md section DSO3",
        },
        "summary": {
            "n_alerts":       len(alerts),
            "n_critical":     len(critical),
            "n_high":         len(high),
            "n_emerging":     len(emerging_zones),
            "n_declining":    len(declining_zones),
            "top_emerging":   [a.zone for a in alerts[:3] if a.emergence_score > 0],
        }
    }


def _build_message(zone, alert_type, pg, vg, price_r, price_p, n_r, n_p) -> str:
    msgs = {
        "emerging":     f"Zone émergente : {zone} — prix +{pg*100:.1f}% et volume +{vg*100:.1f}%. Prix médian : {price_r:,.0f} TND.",
        "price_surge":  f"Hausse de prix à {zone} : +{pg*100:.1f}% ({(price_p or 0):,.0f} → {price_r:,.0f} TND).",
        "volume_surge": f"Forte activité à {zone} : {n_r} annonces (+{vg*100:.1f}% vs période précédente).",
        "declining":    f"Zone en déclin : {zone} — baisse de {abs(pg)*100:.1f}%.",
    }
    return msgs.get(alert_type, f"Activité anormale à {zone}.")


# ══════════════════════════════════════════════════════════════════════════════
# RAPPORT TERRITORIAL COMPLET
# ══════════════════════════════════════════════════════════════════════════════

def generate_territorial_report(df: pd.DataFrame, run_id: str = "unknown",
                                 output_path: str = "data/reports") -> dict:
    """Génère un rapport territorial complet (DSO1+DSO2+DSO3) en JSON."""
    import json, os
    from pathlib import Path
    logger.info(f"[TerritorialTools] Rapport territorial run_id={run_id}")
    df_prep  = prepare_temporal_data(df)
    ts_city  = compute_time_series(df_prep, group_by="city",        freq="M")
    ts_gov   = compute_time_series(df_prep, group_by="governorate", freq="M")
    spatial  = compute_spatial_aggregation(df_prep)
    emerging = detect_emerging_zones(df_prep, group_by="city")
    report   = {
        "run_id": run_id, "generated_at": datetime.utcnow().isoformat(),
        "time_series": {"by_city": ts_city, "by_governorate": ts_gov},
        "spatial":  spatial, "emerging": emerging,
        "global_summary": {
            "total_listings":    len(df_prep),
            "date_range": {
                "start": str(df_prep["date"].min())[:10] if not df_prep.empty else "N/A",
                "end":   str(df_prep["date"].max())[:10] if not df_prep.empty else "N/A",
            },
            "n_cities_covered":  df_prep["city"].nunique()         if "city"         in df_prep.columns else 0,
            "n_gov_covered":     df_prep["governorate"].nunique()   if "governorate"  in df_prep.columns else 0,
            "n_emerging_zones":  emerging["summary"]["n_emerging"],
            "n_alerts":          emerging["summary"]["n_alerts"],
        }
    }
    Path(output_path).mkdir(parents=True, exist_ok=True)
    json_path = os.path.join(output_path, f"territorial_{run_id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"[TerritorialTools] Rapport sauvegardé : {json_path}")
    report["json_path"] = json_path
    return report
