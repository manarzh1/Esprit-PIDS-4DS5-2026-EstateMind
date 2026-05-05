import pandas as pd
import numpy as np

def compute_scores(df: pd.DataFrame, user_profile: dict) -> pd.DataFrame:
    print("   → Scoring BO4 intelligent...")

    # --------------------------
    # SAFE CHECKS (IMPORTANT)
    # --------------------------
    if "price_per_m2" not in df.columns:
        df["price_per_m2"] = df["price_value"] / df["surface_m2"]

    if "roi_norm" not in df.columns:
        df["roi_norm"] = 0.5  # fallback safe

    if "location_score" not in df.columns:
        df["location_score"] = 0.8

    # --------------------------
    # RISK SCORE
    # --------------------------
    df["risk_score"] = 0.0
    df.loc[df["price_value"] < 80000, "risk_score"] += 0.25
    df.loc[df["surface_m2"] > 500, "risk_score"] += 0.20
    df.loc[df["roi_gross"] > 0.09, "risk_score"] += 0.25
    df["risk_score"] = df["risk_score"].clip(0, 1)

    # --------------------------
    # USER MATCH
    # --------------------------
    preferred_cities = [c.lower() for c in user_profile.get("preferred_cities", [])]
    budget = user_profile.get("budget", 450000)

    df["user_match_score"] = df["city"].apply(
        lambda c: 0.45 if any(p in str(c).lower() for p in preferred_cities) else 0.0
    )

    df["user_match_score"] += (1 - (df["price_value"] / budget)).clip(0, 0.8) * 0.25
    df["user_match_score"] += df["roi_norm"] * 0.30
    df["user_match_score"] = df["user_match_score"].clip(0, 1)

    # --------------------------
    # QUALITY BONUS
    # --------------------------
    df["quality_bonus"] = 0.0
    df.loc[(df["surface_m2"] >= 60) & (df["surface_m2"] <= 250), "quality_bonus"] += 0.06
    df.loc[(df["price_value"] >= 90000) & (df["price_value"] <= 450000), "quality_bonus"] += 0.06

    # --------------------------
    # COMPETITION FACTOR
    # --------------------------
    df["competition_penalty"] = 1 / (1 + df["price_per_m2"])

    # --------------------------
    # FINAL SCORE (STABLE VERSION)
    # --------------------------
    df["score"] = (
        0.40 * df["roi_norm"] +
        0.25 * (1 - df["risk_score"]) +
        0.15 * df["location_score"] +
        0.15 * df["user_match_score"] +
        0.05 * df["competition_penalty"] +
        df["quality_bonus"]
    )

    # ❌ IMPORTANT: DO NOT USE rank() (ça casse ton modèle)
    df["score"] = (
        (df["score"] - df["score"].min()) /
        (df["score"].max() - df["score"].min() + 1e-9)
    )

    # --------------------------
    # DECISION SYSTEM
    # --------------------------
    df["decision"] = "HOLD"

    df.loc[df["score"] > 0.75, "decision"] = "BUY"
    df.loc[df["score"] < 0.40, "decision"] = "AVOID"

    return df