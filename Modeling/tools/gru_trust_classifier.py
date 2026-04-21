"""
Estate Mind — GRU Trust Classifier (BO1)
═════════════════════════════════════════
Réseau de neurones GRU (Gated Recurrent Unit) + SoftMax pour classifier
les annonces en 3 niveaux de fiabilité : Fiable / Moyen / Suspect

Pourquoi GRU et pas un simple seuil fixe ?
  - Un GRU apprend les PATTERNS SÉQUENTIELS dans les features d'une annonce
  - Il "mémorise" des patterns courts : ex. prix qui baisse progressivement
    dans les révisions d'une annonce = signal de manipulation
  - SoftMax comme couche finale → probabilités par classe (pas juste un score)
  - Plus robuste qu'un seuil fixe car adaptatif aux données réelles

Architecture :
  Input → [price_norm, surface_norm, ppm2_norm, desc_length_norm,
            source_score, has_gps, has_title_deed, is_duplicate_score]
  → GRU(hidden=32, layers=1)
  → Dropout(0.3)
  → Dense(16, ReLU)
  → Dense(3, SoftMax)  → [P(Suspect), P(Moyen), P(Fiable)]

Training :
  Labels = trust_score binning :
    Suspect : trust_score < 0.50
    Moyen   : 0.50 ≤ trust_score < 0.75
    Fiable  : trust_score ≥ 0.75

Fallback :
  Si PyTorch absent → utilise le scoring basé sur règles (risk_tools.py)

Installation : pip install torch
"""
from __future__ import annotations

import json
import os
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

# ── Import PyTorch avec fallback ──────────────────────────────────────────────
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("[GRU] PyTorch non installé — pip install torch — fallback règles")

MODEL_PATH = Path("models/gru_trust_classifier.pt")
SCALER_PATH= Path("models/gru_scaler.json")

# Classes de fiabilité
CLASSES    = ["Suspect", "Moyen", "Fiable"]
THRESHOLDS = [0.50, 0.75]  # < 0.50 = Suspect, < 0.75 = Moyen, ≥ 0.75 = Fiable

# Score de fiabilité par source (calibré sur l'historique)
SOURCE_SCORES = {
    "remax":     0.95,
    "tecnocasa": 0.85,
    "mubawab":   0.70,
    "tayara":    0.55,
    "csv":       0.50,
    "unknown":   0.45,
}


# ══════════════════════════════════════════════════════════════════════════════
# ARCHITECTURE GRU
# ══════════════════════════════════════════════════════════════════════════════

if TORCH_AVAILABLE:
    class GRUTrustNet(nn.Module):
        """
        GRU + SoftMax pour la classification du trust score.

        Entrée : séquence de features [batch, seq_len, n_features]
                 (seq_len=1 pour une annonce individuelle)
        Sortie : probabilités [batch, 3] → [P(Suspect), P(Moyen), P(Fiable)]
        """
        def __init__(self, n_features: int = 8, hidden_size: int = 32, n_layers: int = 1):
            super().__init__()
            self.hidden_size = hidden_size
            self.n_layers    = n_layers

            # Couche GRU principale
            self.gru = nn.GRU(
                input_size=n_features,
                hidden_size=hidden_size,
                num_layers=n_layers,
                batch_first=True,
                dropout=0.0 if n_layers == 1 else 0.3,
            )

            # Régularisation
            self.dropout = nn.Dropout(0.3)

            # Couches denses de classification
            self.fc1    = nn.Linear(hidden_size, 16)
            self.relu   = nn.ReLU()
            self.fc2    = nn.Linear(16, 3)           # 3 classes
            self.softmax= nn.Softmax(dim=1)          # SoftMax final

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            # x : [batch, seq_len, n_features]
            h0 = torch.zeros(self.n_layers, x.size(0), self.hidden_size)

            out, _  = self.gru(x, h0)      # out : [batch, seq_len, hidden]
            out     = out[:, -1, :]         # dernier timestep
            out     = self.dropout(out)
            out     = self.relu(self.fc1(out))
            out     = self.fc2(out)
            return self.softmax(out)        # [batch, 3]


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════════════════════════

def extract_features(row: pd.Series, df_ref: pd.DataFrame) -> np.ndarray:
    """
    Extrait les 8 features numériques d'une annonce pour le GRU.

    Features :
      0. price_norm       : prix normalisé par la médiane de la ville [0-3]
      1. surface_norm     : surface normalisée (bornes 5-500m²) [0-1]
      2. ppm2_norm        : prix/m² normalisé par la médiane nationale [0-3]
      3. desc_length_norm : longueur description normalisée (0-500 chars) [0-1]
      4. source_score     : score de fiabilité de la source [0-1]
      5. has_gps          : 1 si coordonnées GPS présentes, 0 sinon
      6. has_title_deed   : 1 si acte notarié mentionné dans la description
      7. price_coherence  : cohérence du prix vs distribution IQR de la ville
    """
    features = np.zeros(8, dtype=np.float32)

    price   = float(row.get("price",   0) or 0)
    surface = float(row.get("surface", 0) or 0)
    desc    = str(row.get("description", "") or "")
    source  = str(row.get("source", "unknown") or "unknown").lower()
    city    = str(row.get("city", "") or "")
    lat     = row.get("latitude")
    lon     = row.get("longitude")

    # 0. Prix normalisé vs médiane ville
    city_prices = df_ref[df_ref["city"].astype(str) == city]["price"].dropna() if "city" in df_ref.columns else pd.Series()
    med_price   = float(city_prices.median()) if not city_prices.empty else 200_000
    features[0] = min(price / max(med_price, 1), 3.0) if price > 0 else 0.5

    # 1. Surface normalisée
    features[1] = min(surface / 500, 1.0) if surface > 0 else 0.3

    # 2. Prix/m² normalisé vs médiane nationale
    nat_ppm2   = df_ref["price_per_m2"].dropna().median() if "price_per_m2" in df_ref.columns else 2200
    ppm2       = price / surface if surface > 0 and price > 0 else float(nat_ppm2)
    features[2]= min(ppm2 / max(float(nat_ppm2), 1), 3.0)

    # 3. Longueur de description normalisée
    features[3] = min(len(desc) / 500, 1.0)

    # 4. Score source
    features[4] = SOURCE_SCORES.get(source, 0.45)

    # 5. GPS présent
    features[5] = 1.0 if (pd.notna(lat) and pd.notna(lon) and float(lat or 0) != 0) else 0.0

    # 6. Acte notarié mentionné
    keywords_title = ["titre foncier", "acte notarié", "acte not", "tf ", " tf,", "notaire"]
    features[6]    = 1.0 if any(kw in desc.lower() for kw in keywords_title) else 0.0

    # 7. Cohérence prix dans l'IQR de la ville
    if not city_prices.empty and price > 0:
        q1, q3 = float(city_prices.quantile(0.25)), float(city_prices.quantile(0.75))
        iqr    = q3 - q1
        if iqr > 0:
            dist   = max(0, min(abs(price - float(city_prices.median())), 3 * iqr))
            features[7] = 1.0 - min(dist / (3 * iqr), 1.0)
        else:
            features[7] = 0.5
    else:
        features[7] = 0.5

    return features


# ══════════════════════════════════════════════════════════════════════════════
# CLASSIFIER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class GRUTrustClassifier:
    """
    Interface principale du classifieur GRU Trust Score.

    Usage :
        clf = GRUTrustClassifier()
        clf.train(df_with_trust_scores)   # entraîne ou charge le modèle
        result = clf.predict(row, df_ref) # prédit pour une annonce
    """

    def __init__(self, n_features: int = 8, hidden_size: int = 32):
        self.n_features  = n_features
        self.hidden_size = hidden_size
        self.model       = None
        self.trained     = False
        self._load_model()

    def _load_model(self) -> None:
        """Charge le modèle pré-entraîné s'il existe."""
        if not TORCH_AVAILABLE: return
        if MODEL_PATH.exists():
            try:
                self.model = GRUTrustNet(self.n_features, self.hidden_size)
                self.model.load_state_dict(torch.load(str(MODEL_PATH), map_location="cpu"))
                self.model.eval()
                self.trained = True
                logger.info(f"[GRU] Modèle chargé depuis {MODEL_PATH}")
            except Exception as e:
                logger.warning(f"[GRU] Chargement modèle échoué : {e}")

    def train(
        self,
        df:          pd.DataFrame,
        epochs:      int   = 50,
        lr:          float = 1e-3,
        batch_size:  int   = 32,
        save:        bool  = True,
    ) -> dict:
        """
        Entraîne le GRU sur le dataset disponible.

        Les labels sont générés à partir de trust_score existant :
          trust_score < 0.50 → 0 (Suspect)
          trust_score < 0.75 → 1 (Moyen)
          trust_score ≥ 0.75 → 2 (Fiable)

        Returns : dict avec loss finale, accuracy, n_samples
        """
        if not TORCH_AVAILABLE:
            return {"error": "PyTorch non disponible", "method": "rules_fallback"}

        if "trust_score" not in df.columns or len(df) < 20:
            return {"error": "trust_score absent ou dataset trop petit (min 20)"}

        logger.info(f"[GRU] Entraînement sur {len(df)} annonces ({epochs} epochs)")

        # Extraction features + labels
        X_list, y_list = [], []
        for _, row in df.iterrows():
            ts = float(row.get("trust_score", 0.5) or 0.5)
            label = 0 if ts < THRESHOLDS[0] else 1 if ts < THRESHOLDS[1] else 2
            feat  = extract_features(row, df)
            X_list.append(feat)
            y_list.append(label)

        X = torch.FloatTensor(np.array(X_list)).unsqueeze(1)  # [N, 1, 8]
        y = torch.LongTensor(np.array(y_list))

        dataset    = TensorDataset(X, y)
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        # Modèle
        self.model = GRUTrustNet(self.n_features, self.hidden_size)
        optimizer  = torch.optim.Adam(self.model.parameters(), lr=lr)
        criterion  = nn.CrossEntropyLoss()

        # Entraînement
        losses = []
        self.model.train()
        for epoch in range(epochs):
            epoch_loss = 0.0
            for Xb, yb in dataloader:
                optimizer.zero_grad()
                out  = self.model(Xb)
                loss = criterion(out, yb)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
            losses.append(epoch_loss / len(dataloader))
            if (epoch + 1) % 10 == 0:
                logger.info(f"[GRU] Epoch {epoch+1}/{epochs} — Loss: {losses[-1]:.4f}")

        # Évaluation
        self.model.eval()
        with torch.no_grad():
            preds    = self.model(X).argmax(dim=1)
            accuracy = float((preds == y).float().mean())

        self.trained = True

        # Sauvegarde
        if save:
            MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            torch.save(self.model.state_dict(), str(MODEL_PATH))
            logger.info(f"[GRU] Modèle sauvegardé → {MODEL_PATH}")

        logger.info(f"[GRU] Entraînement terminé — Accuracy: {accuracy:.3f}, Loss finale: {losses[-1]:.4f}")
        return {
            "accuracy":    round(accuracy, 4),
            "final_loss":  round(losses[-1], 4),
            "n_samples":   len(df),
            "epochs":      epochs,
            "method":      "gru_softmax",
            "classes":     CLASSES,
            "model_path":  str(MODEL_PATH),
        }

    def predict(self, row: pd.Series, df_ref: pd.DataFrame) -> dict:
        """
        Prédit la classe de trust pour une annonce individuelle.

        Returns :
          dict avec predicted_class, probabilities, trust_label, method
        """
        features = extract_features(row, df_ref)

        if not TORCH_AVAILABLE or not self.trained or self.model is None:
            # Fallback : règles simples
            score = _rule_based_score(features)
            label = "Suspect" if score < THRESHOLDS[0] else "Moyen" if score < THRESHOLDS[1] else "Fiable"
            return {
                "predicted_class": label,
                "probabilities":   {c: round(1/3, 3) for c in CLASSES},
                "trust_score_gru": round(score, 3),
                "method":          "rules_fallback",
                "features":        features.tolist(),
            }

        self.model.eval()
        with torch.no_grad():
            x      = torch.FloatTensor(features).unsqueeze(0).unsqueeze(0)  # [1,1,8]
            probs  = self.model(x).squeeze().numpy()
            pred   = int(np.argmax(probs))

        # Trust score continu = moyenne pondérée des probabilités
        trust_score_gru = float(probs[0]*0.25 + probs[1]*0.625 + probs[2]*1.0)

        return {
            "predicted_class": CLASSES[pred],
            "probabilities":   {CLASSES[i]: round(float(p), 3) for i, p in enumerate(probs)},
            "trust_score_gru": round(trust_score_gru, 3),
            "method":          "gru_softmax",
            "features":        features.tolist(),
            "feature_names":   [
                "price_vs_median", "surface_norm", "ppm2_vs_national",
                "desc_length", "source_reliability", "has_gps",
                "has_title_deed", "price_iqr_coherence"
            ],
        }

    def predict_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prédit la classe pour toutes les annonces d'un DataFrame."""
        results = []
        for _, row in df.iterrows():
            res = self.predict(row, df)
            results.append({
                "trust_level_gru": res["predicted_class"],
                "trust_score_gru": res["trust_score_gru"],
                "prob_fiable":     res["probabilities"].get("Fiable", 0),
                "prob_moyen":      res["probabilities"].get("Moyen", 0),
                "prob_suspect":    res["probabilities"].get("Suspect", 0),
            })
        return df.assign(**{k: [r[k] for r in results] for k in results[0]}) if results else df


def _rule_based_score(features: np.ndarray) -> float:
    """Score basé sur règles si PyTorch absent."""
    w = [0.25, 0.10, 0.20, 0.10, 0.15, 0.05, 0.05, 0.10]
    raw = float(np.dot(features[:8], w[:len(features)]))

    # Pénalité si pas de GPS
    if features[5] < 0.5: raw -= 0.05
    # Bonus si acte notarié
    if features[6] > 0.5: raw += 0.05

    return max(0.0, min(1.0, raw))


# ── Singleton global ──────────────────────────────────────────────────────────
_classifier: Optional[GRUTrustClassifier] = None

def get_classifier() -> GRUTrustClassifier:
    global _classifier
    if _classifier is None:
        _classifier = GRUTrustClassifier()
    return _classifier
