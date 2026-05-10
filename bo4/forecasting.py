    periods = int(periods)
    periods = max(periods, 12)

    cities = df_grouped["GOUVERNORAT"].unique()

    for city in cities:
        df_city = df_grouped[df_grouped["GOUVERNORAT"] == city].copy()
        df_city = df_city.sort_values("ds")

        if len(df_city) < 8:
            print(f"⚠️ {city}: Pas assez de données historiques ({len(df_city)} obs)")
            continue

        df_prophet = df_city[["ds", "y"]].copy()

        try:
            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=False,
                daily_seasonality=False,
                seasonality_mode="multiplicative",
                interval_width=0.95
            )

            model.fit(df_prophet)

            future = model.make_future_dataframe(
                periods=periods,
                freq="M"
            )

            forecast = model.predict(future)

            last_hist_date = df_city["ds"].max()

            forecast["GOUVERNORAT"] = city
            forecast["is_future"] = forecast["ds"] > last_hist_date
            forecast["yhat"] = forecast["yhat"].clip(lower=0)

            models[city] = model
    months_ahead = int(months_ahead)
    months_ahead = max(months_ahead, 1)

    target_index = months_ahead - 1

    if target_index >= len(future_df):
        target_index = len(future_df) - 1

    projected_m2 = future_df.iloc[target_index]["yhat"]

    if pd.isna(projected_m2) or np.isinf(projected_m2):
        return None

    return max(float(projected_m2), 0)


def integrate_forecast_in_pipeline(
    df_current: pd.DataFrame,
    forecasts: dict,
    horizon_years: int = 5
):
    """Intègre les prévisions Prophet dans ton dataframe principal"""

    df = df_current.copy()

    required_cols = ["price_value", "surface_m2"]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f"Colonnes manquantes dans df_current : {missing_cols}")

    df["price_value"] = pd.to_numeric(
        df["price_value"],
        errors="coerce"
    ).fillna(0)

    df["surface_m2"] = pd.to_numeric(
        df["surface_m2"],
        errors="coerce"
    ).fillna(1)

    df.loc[df["surface_m2"] <= 0, "surface_m2"] = 1

    horizon_years = int(horizon_years)
    horizon_years = max(1, min(horizon_years, 10))

    months_ahead = horizon_years * 12

    def get_city(row):
        return (
            row.get("city")
            or row.get("GOUVERNORAT")
            or row.get("city_name")
            or ""
        )

    def get_projected_price(row):
        city = get_city(row)

        current_price = row.get("price_value", 0)
        surface = row.get("surface_m2", 1)

        projected_m2 = get_projected_price_m2(
            forecasts=forecasts,
            city=city,
            months_ahead=months_ahead
        )

        if projected_m2 is None:
            return current_price

        projected_price = projected_m2 * surface

        if pd.isna(projected_price) or np.isinf(projected_price):
            return current_price

        return max(float(projected_price), float(current_price))

    df["projected_price"] = df.apply(get_projected_price, axis=1)

    df["projected_roi"] = (
        (df["projected_price"] - df["price_value"]) /
        df["price_value"].replace(0, np.nan)
    )

    df["projected_roi"] = (
        df["projected_roi"]
        .replace([np.inf, -np.inf], 0)
        .fillna(0)
        .clip(lower=0, upper=0.30)
    )

    # Aligné avec compute_scores()
    # 20% de croissance future = potentiel excellent
    df["projected_roi_norm"] = (
        df["projected_roi"] / 0.20
    ).clip(0, 1)

    df["projected_roi_percent"] = (
        df["projected_roi"] * 100
    ).round(2)

    print(f"✅ Projections Prophet intégrées avec succès sur {len(df)} biens")

    return df


if __name__ == "__main__":
    print("Testing forecasting module...")