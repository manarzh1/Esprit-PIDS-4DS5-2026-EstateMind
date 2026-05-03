"""
SARIMA Engine — Moteur de prévision des prix immobiliers Tunisie
Adapté depuis l'application Tkinter vers FastAPI
"""
import warnings
import itertools
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import adfuller
from pathlib import Path

warnings.filterwarnings("ignore")

DATA_PATH = Path(__file__).parent.parent / "data" / "immobilier_tunisie_global.csv"

_df_global: pd.DataFrame | None = None
_results_cache: dict = {}


def load_data() -> pd.DataFrame:
    global _df_global
    if _df_global is None:
        df = pd.read_csv(DATA_PATH, sep=";", encoding="utf-8-sig")
        df["DATE_TRIM"] = pd.to_datetime(df["DATE_TRIM"])
        _df_global = df
    return _df_global


def get_gouvernorats() -> list:
    df = load_data()
    return sorted(df["GOUVERNORAT"].dropna().unique().tolist())


def get_serie(gouvernorat: str, variable: str = "PRIX_M2_MEDIAN") -> pd.Series:
    df = load_data()
    df_gov = df[df["GOUVERNORAT"] == gouvernorat].sort_values("DATE_TRIM")
    df_gov = df_gov.dropna(subset=[variable])
    serie = df_gov.set_index("DATE_TRIM")[variable]
    serie.index = pd.DatetimeIndex(serie.index, freq="QS")
    return serie


def fit_and_forecast(
    gouvernorat: str,
    variable: str = "PRIX_M2_MEDIAN",
    order: tuple = (1, 1, 1),
    seasonal_order: tuple = (1, 1, 0, 4),
    horizon: int = 6,
) -> dict:
    cache_key = (gouvernorat, variable, order, seasonal_order, horizon)
    if cache_key in _results_cache:
        return _results_cache[cache_key]

    serie = get_serie(gouvernorat, variable)
    if len(serie) < 8:
        raise ValueError(f"Données insuffisantes pour {gouvernorat}")

    model = SARIMAX(
        endog=serie,
        order=order,
        seasonal_order=seasonal_order,
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    result = model.fit(disp=False, maxiter=200)
    fitted = result.fittedvalues
    forecast_obj = result.get_forecast(steps=horizon)
    pred_mean = forecast_obj.predicted_mean
    ci = forecast_obj.conf_int(alpha=0.05)

    try:
        adf_stat, adf_pval, *_ = adfuller(serie.dropna())
    except Exception:
        adf_stat, adf_pval = float("nan"), float("nan")

    # Préparer les dates pour JSON
    hist_dates = [d.strftime("%Y-%m-%d") for d in serie.index]
    fitted_dates = [d.strftime("%Y-%m-%d") for d in fitted.index]
    pred_dates = [d.strftime("%Y-%m-%d") for d in pred_mean.index]

    out = {
        "gouvernorat": gouvernorat,
        "variable": variable,
        "order": list(order),
        "seasonal_order": list(seasonal_order),
        "aic": round(result.aic, 2),
        "bic": round(result.bic, 2),
        "adf_stat": round(float(adf_stat), 4) if not np.isnan(adf_stat) else None,
        "adf_pval": round(float(adf_pval), 4) if not np.isnan(adf_pval) else None,
        "historique": {
            "dates": hist_dates,
            "valeurs": [round(float(v), 1) for v in serie.values],
        },
        "ajuste": {
            "dates": fitted_dates,
            "valeurs": [round(float(v), 1) for v in fitted.values],
        },
        "prevision": {
            "dates": pred_dates,
            "valeurs": [round(float(v), 1) for v in pred_mean.values],
            "lower": [round(float(v), 1) for v in ci.iloc[:, 0].values],
            "upper": [round(float(v), 1) for v in ci.iloc[:, 1].values],
        },
        "derniere_valeur": round(float(serie.iloc[-1]), 1),
        "prevision_finale": round(float(pred_mean.iloc[-1]), 1),
        "hausse_pct": round((float(pred_mean.iloc[-1]) / float(serie.iloc[-1]) - 1) * 100, 2),
    }
    _results_cache[cache_key] = out
    return out


def get_all_gouvernorats_summary() -> list:
    """Résumé prix actuel + tendance pour tous les gouvernorats (pour la carte)."""
    df = load_data()
    result = []
    for gov in df["GOUVERNORAT"].dropna().unique():
        try:
            serie = get_serie(gov, "PRIX_M2_MEDIAN")
            if len(serie) < 4:
                continue
            prix_actuel = float(serie.iloc[-1])
            prix_an_avant = float(serie.iloc[-5]) if len(serie) >= 5 else float(serie.iloc[0])
            croissance = round((prix_actuel / prix_an_avant - 1) * 100, 1) if prix_an_avant > 0 else 0
            result.append({
                "gouvernorat": gov,
                "prix_median": round(prix_actuel, 0),
                "croissance_yoy": croissance,
                "prix_appt": round(float(df[df["GOUVERNORAT"] == gov]["PRIX_M2_APPT"].dropna().iloc[-1]), 0)
                    if len(df[df["GOUVERNORAT"] == gov]["PRIX_M2_APPT"].dropna()) > 0 else None,
                "prix_maison": round(float(df[df["GOUVERNORAT"] == gov]["PRIX_M2_MAISON"].dropna().iloc[-1]), 0)
                    if len(df[df["GOUVERNORAT"] == gov]["PRIX_M2_MAISON"].dropna()) > 0 else None,
            })
        except Exception:
            continue
    return result
