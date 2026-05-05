import shap
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

def add_xai_explanations(df: pd.DataFrame, user_profile: dict = None) -> pd.DataFrame:
    print(" → Génération d'explications XAI (Investisseur)...")

    if len(df) < 30:
        df["xai_explanation"] = "Explication non disponible (trop peu de biens)."
        return df

    # Features utilisées
    feature_cols = ["roi_norm", "user_match_score", "projected_roi", "price_per_m2", 
                    "quality_bonus", "risk_score", "surface_m2", "competition_penalty"]
    feature_cols = [col for col in feature_cols if col in df.columns]

    X = df[feature_cols].copy()
    y = df["score"].copy()

    # On limite à 800 échantillons pour éviter l'erreur de taille (très suffisant pour SHAP)
    if len(X) > 800:
        X_sample = X.sample(n=800, random_state=42)
        y_sample = y.loc[X_sample.index]
    else:
        X_sample = X
        y_sample = y

    model = RandomForestRegressor(n_estimators=150, random_state=42, max_depth=10, n_jobs=-1)
    model.fit(X_sample, y_sample)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_sample)

    # On ajoute seulement les colonnes SHAP sur l'échantillon (pour éviter l'erreur de longueur)
    for i, col in enumerate(feature_cols):
        df.loc[X_sample.index, f"shap_{col}"] = shap_values[:, i]

    def investor_explanation(row):
        positive = []
        vigilance = []
        for col in feature_cols:
            val = row.get(f"shap_{col}", 0)
            name = col.replace("_", " ").title()
            if val > 0.035:
                positive.append(f"{name} très favorable")
            elif val < -0.03:
                vigilance.append(f"{name} point de vigilance")
        text = "Cette propriété est recommandée car :\n"
        if positive:
            text += "• " + "\n• ".join(positive[:3]) + "\n"
        if vigilance:
            text += "• Vigilance : " + ", ".join(vigilance[:2])
        return text

    df["xai_explanation"] = df.apply(investor_explanation, axis=1)

    print(f" → Explications investisseur générées sur {len(df)} biens")
    return df