"""
Estate Mind — Prophet Price Forecaster (BO1 / BO2)
════════════════════════════════════════════════════
Facebook Prophet pour la prédiction de prix immobiliers à 3 mois.

Pourquoi Prophet et pas ARIMA ou régression linéaire ?
  - Prophet est conçu pour des séries avec tendances et saisonnalités
  - Robuste aux valeurs manquantes (courant dans nos données)
  - Produit des intervalles de confiance (crucial pour l'immobilier)
  - Non-paramétrique : pas d'hypothèse de stationnarité requise
  - Développé par Facebook pour des données business réelles (pas académiques)

Installation : pip install prophet
Fallback    : si Prophet absent, régression polynomiale via numpy
"""
from __future__ import annotations

import warnings
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

warnings.filterwarnings("ignore")

# ── Import Prophet avec fallback gracieux ─────────────────────────────────────
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    try:
        from fbprophet import Prophet   # ancienne version
        PROPHET_AVAILABLE = True
    except ImportError:
        PROPHET_AVAILABLE = False
        logger.warning("[Prophet] Non installé — pip install prophet — fallback régression poly")


def _fallback_forecast(series: pd.Series, periods: int = 90) -> list[dict]:
    """
    Fallback si Prophet non installé.
    Régression polynomiale degré 2 avec intervalle de confiance ±1σ.
    """
    if len(series) < 3:
        return []

    y = series.dropna().values
    x = np.arange(len(y))

    # Régression poly degré 2
    coeffs = np.polyfit(x, y, 2)
    poly   = np.poly1d(coeffs)

    # Résidus pour l'intervalle de confiance
    residuals = y - poly(x)
    sigma     = float(np.std(residuals))

    # Projection
    future_x = np.arange(len(y), len(y) + periods)
    forecast  = []
    base_date = datetime.now()

    for i, fx in enumerate(future_x):
        predicted = float(poly(fx))
        d         = base_date + timedelta(days=i + 1)
        forecast.append({
            "date":   d.strftime("%Y-%m-%d"),
            "yhat":   round(predicted, 0),
            "yhat_lower": round(predicted - 1.96 * sigma, 0),
            "yhat_upper": round(predicted + 1.96 * sigma, 0),
            "method": "poly_fallback",
        })

    return forecast


def forecast_prices(
    df:           pd.DataFrame,
    zone:         str,
    group_by:     str  = "city",
    periods_days: int  = 90,
    freq:         str  = "W",    # W=hebdomadaire, M=mensuel
    confidence:   float= 0.80,
) -> dict:
    """
    Prédit l'évolution des prix immobiliers sur `periods_days` jours
    en utilisant Facebook Prophet.

    Args:
        df            : DataFrame préparé (avec colonne 'date' et 'price')
        zone          : ville ou gouvernorat à analyser
        group_by      : "city" ou "governorate"
        periods_days  : horizon de prédiction en jours (défaut : 90 = 3 mois)
        freq          : fréquence d'agrégation ("W"=hebdo, "M"=mensuel)
        confidence    : intervalle de confiance [0-1] (défaut 0.80 = 80%)

    Returns:
        dict avec :
          - forecast      : liste de points {date, yhat, yhat_lower, yhat_upper}
          - historical    : historique des prix agrégés
          - trend         : "hausse" | "stable" | "baisse"
          - trend_pct     : pourcentage de changement prédit sur l'horizon
          - confidence_interval : largeur moyenne de l'intervalle
          - method        : "prophet" ou "poly_fallback"
          - zone          : zone analysée
          - n_obs         : nombre d'observations utilisées
    """
    if "date" not in df.columns:
        from tools.territorial_tools import prepare_temporal_data
        df = prepare_temporal_data(df)

    # Filtre sur la zone
    col = group_by if group_by in df.columns else "city"
    sub = df[df[col].astype(str).str.lower() == zone.lower()].copy()

    if len(sub) < 5:
        return {"error": f"Données insuffisantes pour {zone} ({len(sub)} obs, minimum 5)"}

    # Agrégation temporelle
    sub = sub.set_index("date")
    agg = sub["price"].resample(freq).median().dropna().reset_index()
    agg.columns = ["ds", "y"]
    agg = agg[agg["y"] > 0]

    if len(agg) < 3:
        return {"error": f"Séries temporelle trop courte pour {zone}"}

    logger.info(f"[Prophet] Forecast pour {zone} — {len(agg)} points, {periods_days}j horizon")

    # Historique pour le retour
    historical = [
        {"date": str(r["ds"])[:10], "price": round(float(r["y"]), 0)}
        for _, r in agg.iterrows()
    ]

    method = "prophet" if PROPHET_AVAILABLE else "poly_fallback"

    if not PROPHET_AVAILABLE:
        forecast_pts = _fallback_forecast(agg["y"], periods=periods_days // 7 if freq == "W" else periods_days // 30)
    else:
        try:
            model = Prophet(
                interval_width=confidence,
                seasonality_mode="multiplicative",  # adapté aux prix immobiliers
                yearly_seasonality=len(agg) >= 12,  # saisonnalité annuelle si assez de données
                weekly_seasonality=False,
                daily_seasonality=False,
                changepoint_prior_scale=0.05,   # rigidité des tendances (faible = stable)
            )

            # Ajoute saisonnalité mensuelle si données hebdo et assez de points
            if freq == "W" and len(agg) >= 8:
                model.add_seasonality(name="monthly", period=30.5, fourier_order=3)

            model.fit(agg)

            # Projection
            periods = periods_days // 7 if freq == "W" else periods_days // 30
            future  = model.make_future_dataframe(periods=periods, freq=freq)
            fc      = model.predict(future)

            # Garde seulement la partie future
            fc_future = fc[fc["ds"] > agg["ds"].max()]

            forecast_pts = [
                {
                    "date":       str(r["ds"])[:10],
                    "yhat":       max(round(float(r["yhat"]), 0), 0),
                    "yhat_lower": max(round(float(r["yhat_lower"]), 0), 0),
                    "yhat_upper": max(round(float(r["yhat_upper"]), 0), 0),
                    "method":     "prophet",
                }
                for _, r in fc_future.iterrows()
            ]

        except Exception as e:
            logger.warning(f"[Prophet] Échec ({e}) → fallback poly")
            forecast_pts = _fallback_forecast(agg["y"], periods=periods_days // 7)
            method = "poly_fallback"

    # Calcul de la tendance prédite
    trend_pct = 0.0
    trend     = "stable"
    if forecast_pts:
        first_pred = forecast_pts[0]["yhat"]
        last_pred  = forecast_pts[-1]["yhat"]
        last_hist  = float(agg["y"].iloc[-1])
        if last_hist > 0:
            trend_pct = (last_pred - last_hist) / last_hist * 100
        trend = "hausse" if trend_pct > 2 else "baisse" if trend_pct < -2 else "stable"

    # Largeur moyenne de l'intervalle de confiance
    ci_widths = [
        p["yhat_upper"] - p["yhat_lower"]
        for p in forecast_pts
        if "yhat_upper" in p and "yhat_lower" in p
    ]
    avg_ci = round(float(np.mean(ci_widths)), 0) if ci_widths else 0

    logger.info(f"[Prophet] {zone} → tendance {trend} ({trend_pct:+.1f}%) sur {periods_days}j")

    return {
        "zone":               zone,
        "group_by":           group_by,
        "forecast":           forecast_pts,
        "historical":         historical,
        "trend":              trend,
        "trend_pct":          round(trend_pct, 2),
        "confidence_interval":avg_ci,
        "horizon_days":       periods_days,
        "method":             method,
        "n_obs":              len(agg),
        "last_known_price":   round(float(agg["y"].iloc[-1]), 0),
        "predicted_price_end":forecast_pts[-1]["yhat"] if forecast_pts else None,
        "prophet_available":  PROPHET_AVAILABLE,
    }


def forecast_multiple_zones(
    df:       pd.DataFrame,
    zones:    list[str],
    group_by: str = "city",
    periods:  int = 90,
) -> dict:
    """Forecast Prophet pour plusieurs zones simultanément."""
    results = {}
    for zone in zones:
        try:
            results[zone] = forecast_prices(df, zone, group_by=group_by, periods_days=periods)
        except Exception as e:
            results[zone] = {"error": str(e), "zone": zone}
    return results
