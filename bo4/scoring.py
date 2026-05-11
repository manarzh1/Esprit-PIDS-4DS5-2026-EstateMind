import pandas as pd
import numpy as np


def compute_scores(df: pd.DataFrame, user_profile: dict) -> pd.DataFrame:
    """
    Scoring compatible avec le pipeline :
    - utilise projected_roi produit avant par simple_arima_projection
    - ne crée pas annual_rent_calc
    - ne normalise pas le score final par lot
    - garde une vraie variabilité entre les biens
    """

    print("   → Scoring BO4 intelligent...")

    df = df.copy()

    required_cols = ["price_value", "surface_m2", "city"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Colonne obligatoire manquante : {col}")

    budget = float(user_profile.get("budget", 450000) or 450000)

    df["price_value"] = pd.to_numeric(df["price_value"], errors="coerce").fillna(0)
    df["surface_m2"] = pd.to_numeric(df["surface_m2"], errors="coerce").fillna(1)
    df.loc[df["surface_m2"] <= 0, "surface_m2"] = 1

    df["price_per_m2"] = (
        df["price_value"] / df["surface_m2"]
    ).replace([np.inf, -np.inf], 0).fillna(0)

    # --------------------------
    # projected_roi venant de simulation.py
    # --------------------------
    if "projected_roi" not in df.columns:
        df["projected_roi"] = 0.0

    df["projected_roi"] = pd.to_numeric(
        df["projected_roi"], errors="coerce"
    ).replace([np.inf, -np.inf], 0).fillna(0)

    if "projected_roi_norm" not in df.columns:
        proj_min = df["projected_roi"].quantile(0.05)
        proj_max = df["projected_roi"].quantile(0.95)

        if proj_max > proj_min:
            df["projected_roi_norm"] = (
                (df["projected_roi"] - proj_min) /
                (proj_max - proj_min)
            ).clip(0, 1)
        else:
            df["projected_roi_norm"] = 0.50
    else:
        df["projected_roi_norm"] = pd.to_numeric(
            df["projected_roi_norm"], errors="coerce"
        ).fillna(0.50).clip(0, 1)

    # --------------------------
    # ROI actuel
    # --------------------------
    if "annual_rent" in df.columns:
        annual_rent = pd.to_numeric(df["annual_rent"], errors="coerce").fillna(0)
    elif "monthly_rent" in df.columns:
        annual_rent = pd.to_numeric(df["monthly_rent"], errors="coerce").fillna(0) * 12
    elif "rent_value" in df.columns:
        annual_rent = pd.to_numeric(df["rent_value"], errors="coerce").fillna(0) * 12
    elif "roi_gross" in df.columns:
        df["roi_gross"] = pd.to_numeric(df["roi_gross"], errors="coerce").fillna(0)
        annual_rent = df["roi_gross"] * df["price_value"]
    else:
        annual_rent = pd.Series(0, index=df.index)

    df["roi_gross"] = (
        annual_rent / df["price_value"].replace(0, np.nan)
    ).replace([np.inf, -np.inf], 0).fillna(0)

    df["roi_percent"] = (df["roi_gross"] * 100).round(2)

    roi_min = df["roi_gross"].quantile(0.05)
    roi_max = df["roi_gross"].quantile(0.95)

    if roi_max > roi_min:
        df["roi_norm"] = (
            (df["roi_gross"] - roi_min) /
            (roi_max - roi_min)
        ).clip(0, 1)
    else:
        df["roi_norm"] = (df["roi_gross"] / 0.07).clip(0, 1)

    # --------------------------
    # Scores secondaires
    # --------------------------
    ppm_min = df["price_per_m2"].quantile(0.05)
    ppm_max = df["price_per_m2"].quantile(0.95)

    if ppm_max > ppm_min:
        df["price_m2_score"] = (
            1 - ((df["price_per_m2"] - ppm_min) / (ppm_max - ppm_min))
        ).clip(0, 1)
    else:
        df["price_m2_score"] = 0.50

    df["budget_score"] = (
        1 - (df["price_value"] / budget)
    ).clip(0, 1)

    if "location_score" not in df.columns:
        df["location_score"] = 0.65
    else:
        df["location_score"] = pd.to_numeric(
            df["location_score"], errors="coerce"
        ).fillna(0.65).clip(0, 1)

    preferred_cities = [
        str(c).strip().lower()
        for c in user_profile.get("preferred_cities", [])
    ]

    df["city_match_score"] = df["city"].apply(
        lambda c: 1.0 if any(p in str(c).lower() for p in preferred_cities) else 0.0
    )

    df["user_match_score"] = (
        0.45 * df["city_match_score"] +
        0.25 * df["budget_score"] +
        0.30 * df["roi_norm"]
    ).clip(0, 1)

    # --------------------------
    # Risk score
    # --------------------------
    df["risk_score"] = 0.0

    df.loc[df["price_value"] < 80000, "risk_score"] += 0.20
    df.loc[df["surface_m2"] > 500, "risk_score"] += 0.15
    df.loc[df["roi_gross"] > 0.12, "risk_score"] += 0.20
    df.loc[annual_rent <= 0, "risk_score"] += 0.25
    df.loc[df["price_value"] > budget * 1.20, "risk_score"] += 0.15

    df["risk_score"] = df["risk_score"].clip(0, 1)

    # --------------------------
    # Quality bonus
    # --------------------------
    df["quality_bonus"] = 0.0

    df.loc[
        (df["surface_m2"] >= 60) &
        (df["surface_m2"] <= 250),
        "quality_bonus"
    ] += 0.03

    df.loc[
        df["roi_gross"].between(0.055, 0.09),
        "quality_bonus"
    ] += 0.03

    df.loc[
        df["price_value"] <= budget,
        "quality_bonus"
    ] += 0.03

    df["quality_bonus"] = df["quality_bonus"].clip(0, 0.09)

    # --------------------------
    # Final score absolu
    # --------------------------
    df["score"] = (
        0.30 * df["roi_norm"] +
        0.18 * df["price_m2_score"] +
        0.15 * df["location_score"] +
        0.13 * df["user_match_score"] +
        0.12 * df["projected_roi_norm"] +
        0.12 * (1 - df["risk_score"]) +
        df["quality_bonus"]
    )

    df["score"] = df["score"].clip(0, 1).round(4)

    # --------------------------
    # Decision
    # --------------------------
    df["decision"] = "HOLD"

    # ── Fallback: use projected_roi when roi_gross is near-zero across the dataset
    # (happens when no rent data is available, causing all roi_gross = 0 → 0 BUY)
    roi_col = "roi_gross"
    if df["roi_gross"].median() < 0.01 and "projected_roi" in df.columns and df["projected_roi"].median() > 0.01:
        print("   ⚠️  roi_gross near-zero → fallback to projected_roi for decisions")
        roi_col = "projected_roi"

    # ── Dynamic score threshold: only top 30% qualify as BUY
    # This prevents min-max normalization from making everything look like a BUY
    score_threshold = max(0.60, float(df["score"].quantile(0.70)))
    roi_threshold   = max(0.05, float(df[roi_col].quantile(0.55)))
    print(f"   📊 Seuils dynamiques → score≥{score_threshold:.3f} | {roi_col}≥{roi_threshold:.4f}")

    # ── BUY: top-tier return + top-tier score + acceptable risk
    df.loc[
        (
            (df[roi_col] >= roi_threshold) &
            (df["score"] >= score_threshold) &
            (df["risk_score"] <= 0.55)
        ),
        "decision"
    ] = "BUY"

    # ── AVOID: weak return OR weak score OR extreme risk
    # Only overrides BUY if risk is truly extreme (>= 0.80)
    avoid_roi   = float(df[roi_col].quantile(0.25))
    avoid_score = float(df["score"].quantile(0.25))
    df.loc[
        (
            (df[roi_col] < avoid_roi) |
            (df["score"] < avoid_score) |
            (df["risk_score"] >= 0.80)
        ),
        "decision"
    ] = "AVOID"

    buy_count   = (df["decision"] == "BUY").sum()
    hold_count  = (df["decision"] == "HOLD").sum()
    avoid_count = (df["decision"] == "AVOID").sum()
    print(f"   ✅ Décisions → BUY: {buy_count} | HOLD: {hold_count} | AVOID: {avoid_count}")

    return df