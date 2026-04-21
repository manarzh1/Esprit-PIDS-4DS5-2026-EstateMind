"""
Estate Mind — SHAP Trust Score Explainer (BO1)
════════════════════════════════════════════════
Explique POURQUOI chaque annonce a son Trust Score.

Pourquoi SHAP ?
  Sans SHAP : "Cette annonce a un Trust Score de 0.673"
  Avec SHAP  : "Score 0.673 car : source Tayara (−0.12), prix cohérent (+0.18),
                description courte (−0.09), pas de GPS (−0.06), surface OK (+0.05)"

SHAP (SHapley Additive exPlanations) vient de la théorie des jeux coopératifs.
Il calcule la contribution marginale de chaque feature à la prédiction finale.
Propriété clé : la somme des contributions SHAP = prédiction − valeur de base.
→ 100% explicable, 100% auditables. Critère fondamental en FinTech/PropTech.

Architecture :
  1. On entraîne un RandomForest sur les features d'annonce → trust_score
  2. SHAP TreeExplainer calcule les valeurs SHAP pour chaque annonce
  3. On retourne les contributions triées par magnitude

Installation : pip install shap scikit-learn
Fallback : si SHAP absent, règles de contribution manuelles
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

try:
    import shap
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("[SHAP] Non installé — pip install shap scikit-learn — fallback règles")

# Features utilisées pour le modèle (mêmes que GRU pour cohérence)
FEATURE_NAMES = [
    "price_vs_median",
    "surface_norm",
    "ppm2_vs_national",
    "desc_length_norm",
    "source_reliability",
    "has_gps",
    "has_title_deed",
    "price_iqr_coherence",
]

FEATURE_LABELS_FR = {
    "price_vs_median":     "Prix vs médiane ville",
    "surface_norm":        "Surface (cohérence)",
    "ppm2_vs_national":    "Prix/m² vs national",
    "desc_length_norm":    "Qualité description",
    "source_reliability":  "Fiabilité source",
    "has_gps":             "Coordonnées GPS",
    "has_title_deed":      "Acte notarié",
    "price_iqr_coherence": "Cohérence prix IQR",
}

SOURCE_SCORES = {
    "remax":0.95,"tecnocasa":0.85,"mubawab":0.70,
    "tayara":0.55,"csv":0.50,"unknown":0.45,
}


@dataclass
class SHAPExplanation:
    trust_score:       float
    base_value:        float
    contributions:     list   # [{"feature","label_fr","shap_value","impact","direction"}]
    top_positive:      list   # features qui augmentent le score
    top_negative:      list   # features qui diminuent le score
    verdict:           str
    explanation_text:  str
    method:            str = "shap"


def _extract_features_df(df: pd.DataFrame) -> pd.DataFrame:
    """Extrait les 8 features pour chaque annonce du dataset."""
    rows = []
    nat_ppm2 = float(df["price_per_m2"].dropna().median()) if "price_per_m2" in df.columns else 2200

    for _, row in df.iterrows():
        price  = float(row.get("price",0) or 0)
        surf   = float(row.get("surface",0) or 0)
        desc   = str(row.get("description","") or "")
        source = str(row.get("source","unknown") or "").lower()
        city   = str(row.get("city","") or "")
        lat    = row.get("latitude")
        lon    = row.get("longitude")

        city_p = df[df["city"].astype(str)==city]["price"].dropna() if "city" in df.columns else pd.Series()
        med_p  = float(city_p.median()) if not city_p.empty else 200_000

        ppm2   = price/surf if surf>0 and price>0 else nat_ppm2
        q1,q3  = (float(city_p.quantile(.25)),float(city_p.quantile(.75))) if not city_p.empty else (100_000,400_000)
        iqr    = q3-q1
        coherence = (1.0 - min(abs(price-float(city_p.median() if not city_p.empty else med_p))/(3*max(iqr,1)),1.0)) if price>0 else 0.5

        rows.append([
            min(price/max(med_p,1),3.0) if price>0 else 0.5,
            min(surf/500,1.0) if surf>0 else 0.3,
            min(ppm2/max(nat_ppm2,1),3.0),
            min(len(desc)/500,1.0),
            SOURCE_SCORES.get(source,0.45),
            1.0 if (pd.notna(lat) and float(lat or 0)!=0) else 0.0,
            1.0 if any(kw in desc.lower() for kw in ["titre foncier","acte notarié"]) else 0.0,
            coherence,
        ])

    return pd.DataFrame(rows, columns=FEATURE_NAMES)


class SHAPExplainer:
    """
    Explique le Trust Score de chaque annonce via SHAP TreeExplainer.

    Workflow :
      1. fit(df)     → entraîne RandomForest sur le dataset
      2. explain(row)→ calcule les contributions SHAP pour une annonce
    """

    def __init__(self):
        self.model   = None
        self.explainer = None
        self.base_value = 0.5
        self.fitted  = False

    def fit(self, df: pd.DataFrame) -> dict:
        """Entraîne le RandomForest sur les annonces avec trust_score connu."""
        if not SHAP_AVAILABLE:
            return {"error": "SHAP/sklearn non disponibles", "method":"fallback"}
        if "trust_score" not in df.columns or len(df) < 20:
            return {"error": "trust_score absent ou dataset trop petit"}

        df_valid = df[df["trust_score"].notna() & df["price"].notna()].copy()
        X = _extract_features_df(df_valid)
        y = df_valid["trust_score"].values

        self.model = RandomForestRegressor(
            n_estimators=100, max_depth=6, random_state=42, n_jobs=-1
        )
        self.model.fit(X, y)
        self.explainer  = shap.TreeExplainer(self.model)
        self.base_value = float(self.model.predict(X).mean())
        self.fitted     = True

        # Score OOB approximatif
        from sklearn.model_selection import cross_val_score
        cv = cross_val_score(self.model, X, y, cv=3, scoring="r2")

        logger.info(f"[SHAP] Modèle entraîné — R²={cv.mean():.3f}, {len(df_valid)} annonces")
        return {
            "r2_cv": round(float(cv.mean()), 4),
            "n_samples": len(df_valid),
            "base_value": round(self.base_value, 3),
            "method": "random_forest+shap",
        }

    def explain(self, row: pd.Series, df_ref: pd.DataFrame) -> SHAPExplanation:
        """Calcule l'explication SHAP pour une annonce."""
        if not SHAP_AVAILABLE or not self.fitted:
            return self._fallback_explain(row, df_ref)

        try:
            # Feature vector
            tmp_df = pd.DataFrame([row.to_dict()])
            X_row  = _extract_features_df(pd.concat([df_ref.head(50), tmp_df], ignore_index=True)).tail(1)

            # Prédiction
            trust_score = float(self.model.predict(X_row)[0])
            trust_score = max(0.0, min(1.0, trust_score))

            # Valeurs SHAP
            shap_vals = self.explainer.shap_values(X_row)[0]  # [8]

            # Construit les contributions
            contributions = []
            for i, (feat, sv) in enumerate(zip(FEATURE_NAMES, shap_vals)):
                contributions.append({
                    "feature":    feat,
                    "label_fr":   FEATURE_LABELS_FR.get(feat, feat),
                    "shap_value": round(float(sv), 4),
                    "feature_val":round(float(X_row.values[0][i]), 3),
                    "impact":     "positif" if sv > 0.005 else "négatif" if sv < -0.005 else "neutre",
                    "direction":  "↑" if sv > 0 else "↓",
                })

            contributions.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
            top_pos = [c for c in contributions if c["impact"]=="positif"][:3]
            top_neg = [c for c in contributions if c["impact"]=="négatif"][:3]

            # Texte explicatif
            pos_txt = ", ".join(f"{c['label_fr']} (+{c['shap_value']:.3f})" for c in top_pos[:2])
            neg_txt = ", ".join(f"{c['label_fr']} ({c['shap_value']:.3f})" for c in top_neg[:2])
            verdict = "Fiable" if trust_score>=.75 else "Moyen" if trust_score>=.5 else "Suspect"
            expl = f"Score {trust_score:.3f} ({verdict}). "
            if pos_txt: expl += f"Points forts : {pos_txt}. "
            if neg_txt: expl += f"Points faibles : {neg_txt}."

            return SHAPExplanation(
                trust_score=round(trust_score,3),
                base_value=round(self.base_value,3),
                contributions=contributions,
                top_positive=top_pos,
                top_negative=top_neg,
                verdict=verdict,
                explanation_text=expl,
                method="shap_tree",
            )

        except Exception as e:
            logger.warning(f"[SHAP] Explain échoué : {e} → fallback")
            return self._fallback_explain(row, df_ref)

    def _fallback_explain(self, row: pd.Series, df_ref: pd.DataFrame) -> SHAPExplanation:
        """Explication par règles si SHAP absent."""
        price  = float(row.get("price",0) or 0)
        surf   = float(row.get("surface",0) or 0)
        desc   = str(row.get("description","") or "")
        source = str(row.get("source","unknown") or "").lower()
        city   = str(row.get("city","") or "")

        city_p = df_ref[df_ref["city"].astype(str)==city]["price"].dropna() if "city" in df_ref.columns else pd.Series()
        med_p  = float(city_p.median()) if not city_p.empty else 200_000

        # Contributions manuelles approchées
        contribs = []
        base = 0.50
        ts   = base

        def _add(feat, val, threshold_ok, delta_ok, delta_bad):
            nonlocal ts
            ok = val >= threshold_ok
            sv = delta_ok if ok else delta_bad
            ts += sv
            contribs.append({
                "feature": feat, "label_fr": FEATURE_LABELS_FR.get(feat,feat),
                "shap_value": round(sv,4), "feature_val": round(val,3),
                "impact":"positif" if sv>0.005 else "négatif" if sv<-0.005 else "neutre",
                "direction":"↑" if sv>0 else "↓",
            })

        src_s = SOURCE_SCORES.get(source,0.45)
        _add("source_reliability",src_s,0.75,+0.12,-0.10)
        pr = (price/max(med_p,1)) if price>0 else 1.0
        _add("price_vs_median",pr,1.5,+0.08,-0.12 if pr<0.3 or pr>2.5 else -0.02)
        _add("desc_length_norm",min(len(desc)/500,1),0.4,+0.07,-0.09)
        lat = row.get("latitude"); has_gps = 1.0 if pd.notna(lat) and float(lat or 0)!=0 else 0.0
        _add("has_gps",has_gps,0.5,+0.05,-0.06)
        has_tf = 1.0 if any(k in desc.lower() for k in ["titre foncier","acte notarié"]) else 0.0
        _add("has_title_deed",has_tf,0.5,+0.08,-0.0)
        _add("surface_norm",min(surf/500,1) if surf>0 else 0.3,0.1,+0.03,-0.04)

        ts = max(0.0,min(1.0,ts))
        contribs.sort(key=lambda x:abs(x["shap_value"]),reverse=True)
        top_pos = [c for c in contribs if c["impact"]=="positif"][:3]
        top_neg = [c for c in contribs if c["impact"]=="négatif"][:3]
        verdict = "Fiable" if ts>=.75 else "Moyen" if ts>=.5 else "Suspect"
        pos_txt = ", ".join(f"{c['label_fr']}" for c in top_pos[:2])
        neg_txt = ", ".join(f"{c['label_fr']}" for c in top_neg[:2])
        expl = f"Score {ts:.3f} ({verdict}). Points forts : {pos_txt}. Points faibles : {neg_txt}."

        return SHAPExplanation(
            trust_score=round(ts,3), base_value=round(base,3),
            contributions=contribs, top_positive=top_pos, top_negative=top_neg,
            verdict=verdict, explanation_text=expl, method="rules_fallback",
        )


# ── Singleton ─────────────────────────────────────────────────────────────────
_explainer: Optional[SHAPExplainer] = None

def get_explainer() -> SHAPExplainer:
    global _explainer
    if _explainer is None:
        _explainer = SHAPExplainer()
    return _explainer
