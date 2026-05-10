import pandas as pd
import numpy as np

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    print("   → Feature Engineering BO4 (version finale réaliste)...")

    df = df.copy()

    # --------------------------
    # CLEANING
    # --------------------------
    df["price_value"] = pd.to_numeric(df["price_value"], errors="coerce")
    df["surface_m2"] = pd.to_numeric(df["surface_m2"], errors="coerce")

    df = df.dropna(subset=["price_value", "surface_m2"])
    df = df[(df["price_value"] > 0) & (df["surface_m2"] > 0)]

    # Filtrage investissements sérieux
    df = df[
        (df["price_value"] >= 95000) & 
        (df["surface_m2"] >= 55) & 
        (df["price_value"] <= 2_500_000)
    ].copy()

    # --------------------------
    # BASIC FEATURES
    # --------------------------
    df["price_per_m2"] = df["price_value"] / df["surface_m2"]

    df["property_type"] = df["property_type"].fillna("unknown").str.lower()
    df["is_terrain"] = df["property_type"].str.contains(
        "terrain|land|plot|parcelle|lot", na=False
    )

    # ✅ Nettoyage colonne city — supprimer les lignes sans ville valide
    if "city" in df.columns:
        df["city"] = df["city"].fillna("").astype(str).str.strip()
        df = df[
            (df["city"] != "") &
            (df["city"].str.lower() != "unknown") &
            (df["city"].str.lower() != "nan") &
            (df["city"].str.lower() != "none")
        ].copy()
        print(f"   → {len(df)} biens avec ville valide")

    # --------------------------
    # RENT ESTIMATION
    # --------------------------
    def estimate_rent(row):
        price = row["price_value"]
        ptype = row["property_type"]

        if row["is_terrain"]:
            yield_rate = 0.038
        elif any(x in ptype for x in ["appart", "studio", "s+"]):
            yield_rate = 0.068
        elif any(x in ptype for x in ["villa", "maison", "dar"]):
            yield_rate = 0.057
        else:
            yield_rate = 0.062

        # pénalité si prix/m² trop élevé
        if row["price_per_m2"] > 7000:
            yield_rate -= 0.01

        monthly = (price * yield_rate) / 12
        return max(monthly, 550)

    df["rent_estimation_monthly"] = df.apply(estimate_rent, axis=1)
    df["annual_rent_est"] = df["rent_estimation_monthly"] * 12

    # --------------------------
    # ROI CALCULATION
    # --------------------------
    df["roi_gross"] = df["annual_rent_est"] / df["price_value"]

    # 🔥 Ajout bruit réaliste (marché)
    df["roi_gross"] *= np.random.normal(1.0, 0.02, size=len(df))

    # 🔒 Bornes réalistes (important)
    df["roi_gross"] = df["roi_gross"].clip(0.048, 0.092)

    # Normalisation
    df["roi_norm"] = df["roi_gross"].rank(pct=True)

    # --------------------------
    # LOCATION SCORE (simple baseline)
    # --------------------------
    df["location_score"] = 0.82

    # --------------------------
    # LOGS
    # --------------------------
    print(f"   → {len(df)} biens conservés")
    print(f"   → ROI moyen: {df['roi_gross'].mean():.4f}")

    return df