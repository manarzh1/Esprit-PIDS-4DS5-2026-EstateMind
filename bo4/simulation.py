import pandas as pd
import numpy as np

# Taux de croissance réalistes par ville (basé sur données marché tunisien)
CITY_GROWTH_RATES = {
    "tunis": 0.048,
    "la marsa": 0.052,
    "les berges du lac": 0.055,
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
    "sousse": 0.010,
    "monastir": 0.011,
    "nabeul": 0.012,
    "hammamet": 0.011,
    "default": 0.013,
}


def get_city_growth(city_name: str) -> tuple:
    """Retourne (growth_rate, volatility) pour une ville donnée."""
    city_lower = str(city_name).lower().strip()

    # Recherche partielle
    for key in CITY_GROWTH_RATES:
        if key in city_lower or city_lower in key:
            return CITY_GROWTH_RATES[key], CITY_VOLATILITY.get(key, 0.012)

    return CITY_GROWTH_RATES["default"], CITY_VOLATILITY["default"]


def simple_arima_projection(df: pd.DataFrame, horizon_years: int = 5) -> pd.DataFrame:
    """
    Projection temporelle différenciée par ville.
    Simule un modèle Prophet-like avec croissance + saisonnalité.
    """
    print(f"   → Projection temporelle par ville ({horizon_years} ans)...")

    df = df.copy()

    projected_prices = []
    projected_rois = []

    for _, row in df.iterrows():
        city = row.get("city", "default")
        base_growth, volatility = get_city_growth(city)

        # Ajustement selon objectif (si disponible dans le contexte)
        # On simule une trajectoire annuelle avec bruit
        yearly_returns = []
        for year in range(1, horizon_years + 1):
            annual_noise = np.random.normal(0, volatility)
            # Légère mean-reversion
            adjusted_growth = base_growth + annual_noise * (1 - 0.1 * year)
            yearly_returns.append(adjusted_growth)

        compound_growth = np.prod([1 + r for r in yearly_returns])
        projected_price = row["price_value"] * compound_growth

        # ROI projeté = ROI actuel × facteur de croissance du marché
        roi_growth_factor = 1 + np.mean(yearly_returns) * 0.8
        projected_roi = row["roi_gross"] * roi_growth_factor
        projected_roi = np.clip(projected_roi, 0.040, 0.115)

        projected_prices.append(projected_price)
        projected_rois.append(projected_roi)

    df["projected_price"] = projected_prices
    df["projected_roi"] = projected_rois

    # Statistiques par ville
    city_stats = df.groupby("city")["projected_roi"].mean().sort_values(ascending=False)
    print(f"   → ROI moyen projeté global : {df['projected_roi'].mean():.4f}")
    print(f"   → Meilleures villes (ROI projeté) :")
    for city, roi in city_stats.head(5).items():
        print(f"      • {city}: {roi:.4f}")

    return df


def compute_backtest_metrics(df: pd.DataFrame) -> dict:
    """
    Simule un backtesting sur données historiques synthétiques.
    Retourne MAE, precision top5, ROI simulé.
    """
    np.random.seed(42)
    n = min(200, len(df))
    sample = df.sample(n).copy()

    # Simuler "vraies" valeurs avec bruit
    true_roi = sample["roi_gross"] * np.random.normal(1.0, 0.05, size=n)
    pred_roi = sample["projected_roi"]

    mae = float(np.abs(true_roi.values - pred_roi.values).mean())
    mape = float((np.abs(true_roi.values - pred_roi.values) / (true_roi.values + 1e-9)).mean() * 100)

    # Precision top5: est-ce que les 5 mieux scorés sont bien dans le top 10 réel?
    top5_pred = sample.nlargest(5, "score").index
    top10_real = sample.nlargest(10, "roi_gross").index
    precision_top5 = len(set(top5_pred) & set(top10_real)) / 5

    avg_roi_simulated = float(sample["projected_roi"].mean())

    return {
        "MAE": round(mae, 5),
        "MAPE (%)": round(mape, 2),
        "Precision Top5": round(precision_top5, 2),
        "ROI simulé moyen": round(avg_roi_simulated, 4),
        "Nb biens testés": n,
    }