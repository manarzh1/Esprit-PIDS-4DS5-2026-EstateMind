"""
Estate Mind — Anomaly Detector + Micro-Quartiers (BO1 + BO2)
══════════════════════════════════════════════════════════════

① Isolation Forest (BO1 — Anomaly Detection)
   Détecte les annonces statistiquement aberrantes SANS règles prédéfinies.
   Avantage vs règles : trouve des combinaisons impossibles que les règles
   ne voient pas. Ex: surface=80m², rooms=12, prix=95000 → chacun OK seul,
   l'ensemble est impossible.

② DBSCAN Micro-Quartiers (BO2 — Spatial Clustering)
   Density-Based Spatial Clustering of Applications with Noise.
   Découvre les vrais micro-marchés locaux à partir des coordonnées GPS + prix.
   Avantage vs frontières administratives : "Lac 2" et "Berges du Lac" sont
   le même marché, même s'ils sont dans deux arrondissements différents.
   Annonces sans voisins proches → "bruit" (outliers spatiaux).

Installation : pip install scikit-learn
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from loguru import logger
from typing import Optional

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.cluster import DBSCAN
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("[AnomalyDetector] sklearn non installé — pip install scikit-learn")

# ══════════════════════════════════════════════════════════════════════════════
# ① ISOLATION FOREST
# ══════════════════════════════════════════════════════════════════════════════

def detect_anomalies(
    df:             pd.DataFrame,
    contamination:  float = 0.05,   # 5% d'annonces supposées anormales
    n_estimators:   int   = 100,
) -> pd.DataFrame:
    """
    Détecte les annonces anormales via Isolation Forest.

    Pourquoi Isolation Forest ?
      Algorithme basé sur le principe qu'une anomalie est "facile à isoler".
      Il construit des arbres aléatoires et mesure combien de coupures
      sont nécessaires pour isoler chaque point. Un point isolé en peu
      de coupures = anomalie. Non-paramétrique, pas d'hypothèse de distribution.

    Features utilisées :
      - price          : prix de vente
      - surface        : surface habitable
      - price_per_m2   : prix au m²
      - rooms          : nombre de pièces (si disponible)
      - desc_length    : longueur de la description

    Returns : df avec colonnes anomaly_score [-1;0] et is_anomaly [bool]
      anomaly_score < 0     → anormal (plus négatif = plus anormal)
      anomaly_score proche 0→ normal
    """
    df = df.copy()

    if not SKLEARN_AVAILABLE:
        logger.warning("[IsolationForest] sklearn absent — fallback règles")
        return _anomaly_fallback(df)

    # Features numériques robustes
    features = []
    feature_cols = []

    for col, alt in [("price","price_value"),("surface","surface_m2"),("price_per_m2",None)]:
        actual = col if col in df.columns else (alt if alt and alt in df.columns else None)
        if actual:
            s = pd.to_numeric(df[actual], errors="coerce")
            features.append(s.fillna(s.median()))
            feature_cols.append(col)

    if "rooms" in df.columns:
        s = pd.to_numeric(df["rooms"], errors="coerce")
        features.append(s.fillna(s.median()))
        feature_cols.append("rooms")

    if "description" in df.columns:
        features.append(df["description"].astype(str).str.len().clip(0, 2000))
        feature_cols.append("desc_length")

    if len(features) < 2:
        logger.warning("[IsolationForest] Pas assez de features — fallback")
        return _anomaly_fallback(df)

    X = np.column_stack(features)

    # Normalisation
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Isolation Forest
    iso = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    iso.fit(X_scaled)

    df["anomaly_score"] = iso.score_samples(X_scaled)   # [-0.5 ; 0] typiquement
    df["is_anomaly"]    = iso.predict(X_scaled) == -1   # True si anomalie
    df["anomaly_severity"] = df["anomaly_score"].apply(
        lambda s: "critique" if s < -0.6 else "élevée" if s < -0.4 else "faible"
    )

    n_anom = int(df["is_anomaly"].sum())
    logger.info(f"[IsolationForest] {n_anom} anomalies détectées ({contamination*100:.0f}% expected) sur {len(df)} annonces")
    return df


def _anomaly_fallback(df: pd.DataFrame) -> pd.DataFrame:
    """Règles simples si Isolation Forest absent."""
    df = df.copy()
    df["is_anomaly"]       = False
    df["anomaly_score"]    = -0.1
    df["anomaly_severity"] = "faible"

    if "price" in df.columns and "surface" in df.columns:
        price = pd.to_numeric(df["price"], errors="coerce").fillna(0)
        surf  = pd.to_numeric(df["surface"], errors="coerce").fillna(0)
        ppm2  = price / surf.replace(0, np.nan)

        nat_med = float(ppm2.dropna().median()) if ppm2.notna().any() else 2200
        z_score = abs((ppm2 - nat_med) / max(float(ppm2.dropna().std()), 1))

        df["is_anomaly"]    = z_score > 3
        df["anomaly_score"] = (-z_score / 10).clip(-1, 0)
        df["anomaly_severity"] = df["anomaly_score"].apply(
            lambda s: "critique" if s < -0.3 else "élevée" if s < -0.2 else "faible"
        )

    return df


def get_anomaly_report(df: pd.DataFrame) -> dict:
    """Rapport structuré des anomalies détectées."""
    if "is_anomaly" not in df.columns:
        df = detect_anomalies(df)

    anomalies = df[df["is_anomaly"]].copy()
    if anomalies.empty:
        return {"anomalies": [], "total": 0, "summary": {}}

    anomalies = anomalies.sort_values("anomaly_score")

    result = []
    for _, row in anomalies.head(30).iterrows():
        price = float(row.get("price",0) or 0)
        surf  = float(row.get("surface",0) or 0)
        ppm2  = price/surf if surf>0 and price>0 else 0

        # Raison probable (heuristique post-Isolation Forest)
        reasons = []
        if price < 5000 and price > 0: reasons.append("Prix anormalement bas")
        if price > 5_000_000:           reasons.append("Prix anormalement élevé")
        if surf > 3000:                 reasons.append("Surface aberrante")
        if ppm2 > 15000:                reasons.append("Prix/m² extrême")
        if ppm2 < 100 and ppm2 > 0:    reasons.append("Prix/m² suspect (trop bas)")
        if not reasons:                 reasons.append("Combinaison de features inhabituelle")

        result.append({
            "title":           str(row.get("title",""))[:70],
            "city":            str(row.get("city","—")),
            "property_type":   str(row.get("property_type","autre")).replace("_"," "),
            "price":           round(price, 0),
            "surface":         round(surf, 1),
            "price_per_m2":    round(ppm2, 0) if ppm2 > 0 else None,
            "anomaly_score":   round(float(row["anomaly_score"]), 4),
            "anomaly_severity":str(row.get("anomaly_severity","faible")),
            "reasons":         reasons,
            "url":             str(row.get("url","#")),
            "trust_score":     round(float(row.get("trust_score",0.5) or 0.5), 3),
        })

    sev_counts = anomalies["anomaly_severity"].value_counts().to_dict()

    return {
        "anomalies": result,
        "total":     len(anomalies),
        "summary": {
            "pct_anomalies":       round(len(anomalies)/max(len(df),1)*100, 1),
            "critique":            sev_counts.get("critique", 0),
            "elevee":              sev_counts.get("élevée", 0),
            "faible":              sev_counts.get("faible", 0),
            "method":              "isolation_forest" if SKLEARN_AVAILABLE else "rules_fallback",
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# ② DBSCAN MICRO-QUARTIERS
# ══════════════════════════════════════════════════════════════════════════════

def detect_micro_markets(
    df:          pd.DataFrame,
    eps_km:      float = 2.0,    # rayon en km pour regrouper les annonces
    min_samples: int   = 5,      # min annonces pour former un micro-marché
) -> dict:
    """
    Identifie les micro-marchés immobiliers réels via DBSCAN.

    DBSCAN ne nécessite pas de spécifier le nombre de clusters à l'avance.
    Il découvre automatiquement les zones denses et marque les annonces
    isolées comme "bruit" (label -1).

    eps_km     : distance maximale (km) entre deux annonces du même cluster.
                 2km = "à pieds" → cohérent avec la notion de quartier.
    min_samples: nombre minimum d'annonces pour qu'une zone soit un marché.
                 5 est le minimum raisonnable (évite les micro-clusters d'1-2 biens).

    Returns : dict avec clusters, stats par cluster, annonces non clusterisées
    """
    if not SKLEARN_AVAILABLE:
        return {"error": "sklearn non disponible", "clusters": [], "n_clusters": 0}

    # Filtre sur les annonces avec coordonnées GPS valides
    gps_cols = ["latitude","longitude"]
    if not all(c in df.columns for c in gps_cols):
        return {"error": "Colonnes latitude/longitude absentes", "clusters": [], "n_clusters": 0}

    df_gps = df[
        df["latitude"].notna() & df["longitude"].notna() &
        (df["latitude"].astype(float) != 0) &
        (df["longitude"].astype(float) != 0)
    ].copy()

    if len(df_gps) < min_samples * 2:
        return {"error": f"Pas assez d'annonces géolocalisées ({len(df_gps)})", "clusters":[], "n_clusters":0}

    # Coordonnées en radians pour haversine
    coords = df_gps[["latitude","longitude"]].astype(float).values
    coords_rad = np.radians(coords)

    # DBSCAN avec distance haversine (géodésique)
    # eps en radians : eps_km / rayon_terre_km
    eps_rad = eps_km / 6371.0

    db = DBSCAN(
        eps=eps_rad,
        min_samples=min_samples,
        algorithm="ball_tree",
        metric="haversine",
        n_jobs=-1,
    )
    labels = db.fit_predict(coords_rad)
    df_gps["cluster_id"] = labels

    # Statistiques par cluster
    n_clusters = int(max(labels) + 1) if max(labels) >= 0 else 0
    n_noise    = int((labels == -1).sum())

    clusters = []
    for cid in range(n_clusters):
        c_df    = df_gps[df_gps["cluster_id"] == cid]
        prices  = c_df["price"].dropna() if "price" in c_df.columns else pd.Series()
        ppm2s   = c_df["price_per_m2"].dropna() if "price_per_m2" in c_df.columns else pd.Series()
        cities  = c_df["city"].value_counts().head(3).to_dict() if "city" in c_df.columns else {}

        # Centre du cluster
        lat_c = float(c_df["latitude"].mean())
        lon_c = float(c_df["longitude"].mean())

        # Rayon approx (distance max au centroïde, en km)
        dists = np.sqrt(
            (c_df["latitude"].astype(float) - lat_c)**2 +
            (c_df["longitude"].astype(float) - lon_c)**2
        ) * 111  # 1° ≈ 111km
        radius_km = float(dists.max()) if len(dists) > 0 else 0

        # Nom automatique du cluster (ville dominante)
        top_city  = c_df["city"].mode().iloc[0] if "city" in c_df.columns and not c_df["city"].empty else f"Cluster {cid}"
        ptype_top = c_df["property_type"].mode().iloc[0] if "property_type" in c_df.columns and not c_df["property_type"].empty else "mixte"

        # Classification du marché
        if not prices.empty and not ppm2s.empty:
            p50  = float(ppm2s.median())
            p75g = float(df_gps["price_per_m2"].dropna().quantile(0.75)) if "price_per_m2" in df_gps.columns else 3000
            tier = "premium" if p50 > p75g else "standard" if p50 > p75g*0.5 else "accessible"
        else:
            tier = "inconnu"

        clusters.append({
            "cluster_id":      cid,
            "name":            f"{top_city} — Micro-marché {cid+1}",
            "n_listings":      len(c_df),
            "center_lat":      round(lat_c, 5),
            "center_lon":      round(lon_c, 5),
            "radius_km":       round(radius_km, 2),
            "top_cities":      cities,
            "dominant_type":   str(ptype_top).replace("_"," "),
            "median_price":    round(float(prices.median()), 0) if not prices.empty else None,
            "median_ppm2":     round(float(ppm2s.median()), 0) if not ppm2s.empty else None,
            "market_tier":     tier,
            "listings_sample": c_df[["title","city","price","url"]].head(3).to_dict("records"),
        })

    # Trie par volume
    clusters.sort(key=lambda c: c["n_listings"], reverse=True)

    logger.info(f"[DBSCAN] {n_clusters} micro-marchés · {n_noise} annonces hors cluster · eps={eps_km}km")

    return {
        "clusters":     clusters,
        "n_clusters":   n_clusters,
        "n_noise":      n_noise,
        "n_clustered":  len(df_gps) - n_noise,
        "pct_covered":  round((len(df_gps)-n_noise)/max(len(df_gps),1)*100, 1),
        "params": {
            "eps_km":       eps_km,
            "min_samples":  min_samples,
            "method":       "dbscan_haversine",
        },
        "interpretation": (
            f"{n_clusters} micro-marchés identifiés. "
            f"{len(df_gps)-n_noise} annonces sur {len(df_gps)} géolocalisées couvertes ({round((len(df_gps)-n_noise)/max(len(df_gps),1)*100,0):.0f}%). "
            f"{n_noise} annonces isolées (pas dans un marché dense)."
        ),
    }
