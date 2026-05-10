import pandas as pd
import numpy as np


# =========================================================
# Paramètres marché par ville
# =========================================================
CITY_GROWTH_RATES = {
    "tunis": 0.048,
    "la marsa": 0.052,
    "les berges du lac": 0.055,
    "lac": 0.055,
    "ariana": 0.044,
    "sousse": 0.042,
    "sousse ville": 0.042,
    "hammam sousse": 0.040,
    "monastir": 0.038,
    "monastir ville": 0.038,
    "nabeul": 0.035,
    "hammamet": 0.037,
    "sfax": 0.032,
    "bizerte": 0.030,
    "default": 0.033,
}

CITY_VOLATILITY = {
    "tunis": 0.008,
    "la marsa": 0.009,
    "les berges du lac": 0.010,
    "lac": 0.010,
    "ariana": 0.009,
    "sousse": 0.010,
    "hammam sousse": 0.010,
    "monastir": 0.011,
    "nabeul": 0.012,
    "hammamet": 0.011,
    "sfax": 0.012,
    "bizerte": 0.013,
    "default": 0.013,
}


def get_city_growth(city_name: str) -> tuple:
    """Retourne le taux de croissance annuel et la volatilité selon la ville."""
    city_lower = str(city_name).lower().strip()

    for key in CITY_GROWTH_RATES:
        if key != "default" and (key in city_lower or city_lower in key):
            return CITY_GROWTH_RATES[key], CITY_VOLATILITY.get(key, 0.012)

    return CITY_GROWTH_RATES["default"], CITY_VOLATILITY["default"]


def _normalize_series(s: pd.Series, default: float = 0.5) -> pd.Series:
    """Normalisation robuste 0-1 avec fallback."""
    s = pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan)

    if s.dropna().empty:
        return pd.Series(default, index=s.index)

    min_val = s.quantile(0.05)
    max_val = s.quantile(0.95)

    if max_val <= min_val:
        return pd.Series(default, index=s.index)

    return ((s - min_val) / (max_val - min_val)).clip(0, 1).fillna(default)


def simple_arima_projection(df: pd.DataFrame, horizon_years: int = 5) -> pd.DataFrame:
    """
    Projection robuste compatible pipeline BO4.

    Produit :
    - projected_price
    - projected_value_gain
    - projected_roi
    - projected_roi_norm
    - market_growth_rate
    - market_risk
    - projection_confidence

    Important :
    projected_roi ici = rendement locatif futur estimé,
    pas seulement croissance du prix.
    """

    print(f"   → Projection temporelle par ville ({horizon_years} ans)...")

    df = df.copy()

    horizon_years = int(horizon_years)
    horizon_years = max(1, min(horizon_years, 10))

    required_cols = ["price_value", "surface_m2", "city"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Colonne obligatoire manquante dans simulation.py : {col}")

    df["price_value"] = pd.to_numeric(df["price_value"], errors="coerce").fillna(0)
    df["surface_m2"] = pd.to_numeric(df["surface_m2"], errors="coerce").fillna(1)
    df.loc[df["surface_m2"] <= 0, "surface_m2"] = 1

    if "price_per_m2" not in df.columns:
        df["price_per_m2"] = df["price_value"] / df["surface_m2"]

    df["price_per_m2"] = pd.to_numeric(
        df["price_per_m2"], errors="coerce"
    ).replace([np.inf, -np.inf], 0).fillna(0)

    # ROI actuel disponible ou recalculé
    if "roi_gross" in df.columns:
        df["roi_gross"] = pd.to_numeric(df["roi_gross"], errors="coerce").fillna(0)
    elif "annual_rent" in df.columns:
        annual_rent = pd.to_numeric(df["annual_rent"], errors="coerce").fillna(0)
        df["roi_gross"] = annual_rent / df["price_value"].replace(0, np.nan)
        df["roi_gross"] = df["roi_gross"].replace([np.inf, -np.inf], 0).fillna(0)
    elif "monthly_rent" in df.columns:
        annual_rent = pd.to_numeric(df["monthly_rent"], errors="coerce").fillna(0) * 12
        df["roi_gross"] = annual_rent / df["price_value"].replace(0, np.nan)
        df["roi_gross"] = df["roi_gross"].replace([np.inf, -np.inf], 0).fillna(0)
    elif "rent_value" in df.columns:
        annual_rent = pd.to_numeric(df["rent_value"], errors="coerce").fillna(0) * 12
        df["roi_gross"] = annual_rent / df["price_value"].replace(0, np.nan)
        df["roi_gross"] = df["roi_gross"].replace([np.inf, -np.inf], 0).fillna(0)
    else:
        df["roi_gross"] = 0.06

    df["roi_gross"] = df["roi_gross"].clip(0, 0.20)

    # Normalisations utiles
    price_m2_norm = _normalize_series(df["price_per_m2"], default=0.5)
    undervalue_score = (1 - price_m2_norm).clip(0, 1)

    surface_norm = _normalize_series(df["surface_m2"], default=0.5)

    if "location_score" in df.columns:
        location_score = pd.to_numeric(
            df["location_score"], errors="coerce"
        ).fillna(0.65).clip(0, 1)
    else:
        location_score = pd.Series(0.65, index=df.index)

    # Seed fixe pour résultats stables à chaque run
    rng = np.random.default_rng(42)

    projected_prices = []
    projected_value_gains = []
    projected_rois = []
    market_growth_rates = []
    market_risks = []
    projection_confidences = []

    for i, row in df.iterrows():
        city = row.get("city", "default")
        base_growth, volatility = get_city_growth(city)

        price_value = float(row.get("price_value", 0))
        roi_current = float(row.get("roi_gross", 0.06))

        undervalue = float(undervalue_score.loc[i])
        surface_factor = float(surface_norm.loc[i])
        loc_factor = float(location_score.loc[i])

        # Ajustement croissance annuelle
        # Bien sous-évalué + bonne localisation = meilleure croissance
        adjusted_growth = (
            base_growth
            + 0.010 * undervalue
            + 0.006 * loc_factor
            - 0.004 * surface_factor
        )

        adjusted_growth = float(np.clip(adjusted_growth, 0.015, 0.075))

        yearly_returns = []

        for year in range(1, horizon_years + 1):
            noise = rng.normal(0, volatility)

            # mean reversion légère avec le temps
            yearly_growth = adjusted_growth + noise * max(0.45, 1 - 0.08 * year)

            yearly_growth = float(np.clip(yearly_growth, -0.02, 0.10))
            yearly_returns.append(yearly_growth)

        compound_growth = float(np.prod([1 + r for r in yearly_returns]) - 1)

        projected_price = price_value * (1 + compound_growth)
        projected_value_gain = projected_price - price_value

        # Projection du ROI locatif futur
        # Un bien sous-évalué et bien localisé garde/améliore son ROI.
        rent_growth_factor = (
            1
            + 0.35 * compound_growth
            + 0.08 * undervalue
            + 0.04 * loc_factor
        )

        projected_roi = roi_current * rent_growth_factor

        # Garder une fourchette métier réaliste
        projected_roi = float(np.clip(projected_roi, 0.025, 0.14))

        # Risque marché : volatilité + prix très cher/m2 + ROI trop élevé
        market_risk = (
            0.35 * min(volatility / 0.015, 1)
            + 0.35 * price_m2_norm.loc[i]
            + 0.30 * (1 if roi_current > 0.12 else 0)
        )
        market_risk = float(np.clip(market_risk, 0, 1))

        projection_confidence = float(np.clip(1 - market_risk, 0.20, 0.95))

        projected_prices.append(projected_price)
        projected_value_gains.append(projected_value_gain)
        projected_rois.append(projected_roi)
        market_growth_rates.append(compound_growth)
        market_risks.append(market_risk)
        projection_confidences.append(projection_confidence)

    df["projected_price"] = projected_prices
    df["projected_value_gain"] = projected_value_gains
    df["projected_roi"] = projected_rois
    df["market_growth_rate"] = market_growth_rates
    df["market_risk"] = market_risks
    df["projection_confidence"] = projection_confidences

    df["projected_roi"] = (
        pd.to_numeric(df["projected_roi"], errors="coerce")
        .replace([np.inf, -np.inf], 0)
        .fillna(0)
        .clip(0.025, 0.14)
    )

    df["projected_roi_norm"] = _normalize_series(
        df["projected_roi"],
        default=0.5
    )

    df["projected_roi_percent"] = (df["projected_roi"] * 100).round(2)
    df["market_growth_percent"] = (df["market_growth_rate"] * 100).round(2)

    print(f"   → ROI moyen projeté global : {df['projected_roi'].mean():.4f}")
    print(f"   → Croissance valeur moyenne : {df['market_growth_rate'].mean():.4f}")

    if "city" in df.columns:
        city_stats = (
            df.groupby("city")["projected_roi"]
            .mean()
            .sort_values(ascending=False)
        )

        print("   → Meilleures villes selon ROI projeté :")
        for city, roi in city_stats.head(5).items():
            print(f"      • {city}: {roi:.4f}")

    return df


def compute_backtest_metrics(df: pd.DataFrame) -> dict:
    """
    Backtesting synthétique robuste.
    Compatible avec projected_roi, roi_gross et score.
    """

    if len(df) == 0:
        return {
            "MAE": 0.0,
            "MAPE (%)": 0.0,
            "Precision Top5": 0.0,
            "ROI simulé moyen": 0.0,
            "Nb biens testés": 0,
        }

    np.random.seed(42)

    n = min(200, len(df))
    sample = df.sample(n, random_state=42).copy()

    if "roi_gross" not in sample.columns:
        sample["roi_gross"] = 0.06

    if "projected_roi" not in sample.columns:
        sample["projected_roi"] = sample["roi_gross"]

    if "score" not in sample.columns:
        sample["score"] = sample["projected_roi"]

    true_roi = sample["roi_gross"] * np.random.normal(1.0, 0.05, size=n)
    pred_roi = sample["projected_roi"]

    mae = float(np.abs(true_roi.values - pred_roi.values).mean())

    mape = float(
        (
            np.abs(true_roi.values - pred_roi.values) /
            (np.abs(true_roi.values) + 1e-9)
        ).mean() * 100
    )

    top_k = min(5, n)
    real_k = min(10, n)

    top_pred = sample.nlargest(top_k, "score").index
    top_real = sample.nlargest(real_k, "roi_gross").index

    precision_top5 = len(set(top_pred) & set(top_real)) / top_k if top_k > 0 else 0

    avg_roi_simulated = float(sample["projected_roi"].mean())

    return {
        "MAE": round(mae, 5),
        "MAPE (%)": round(mape, 2),
        "Precision Top5": round(precision_top5, 2),
        "ROI simulé moyen": round(avg_roi_simulated, 4),
        "Nb biens testés": int(n),
    }