"""
app/services/nlp/naive_bayes.py
================================
Classifieur Naïve Bayes multinomial — FROM SCRATCH.
N-grammes (unigrams + bigrams + trigrams) + Laplace smoothing.

FORMULE (DSO3 — explicabilité) :
  log P(c|d) = log P(c) + Σ count(t,d) × log P(t|c)
  P(t|c) Laplace = (count(t,c) + 1) / (total_c + |V|)
"""

import math, os, pickle, re
from collections import Counter

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "models_pkl", "nb_model.pkl")

INTENT_LABELS = [
    "price_estimation", "investment_analysis", "location_analysis",
    "legal_verification", "report_generation", "general_query",
]

def tokenize(text: str) -> list:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return [t for t in text.split() if len(t) > 1]

def get_features(text: str, ngram_range=(1, 3)) -> Counter:
    tokens = tokenize(text)
    feats = Counter()
    for n in range(ngram_range[0], ngram_range[1] + 1):
        if n == 1:
            feats.update(tokens)
        else:
            feats.update(["_".join(tokens[i:i+n]) for i in range(len(tokens)-n+1)])
    return feats


class NaiveBayesClassifier:
    def __init__(self, ngram_range=(1, 3)):
        self.ngram_range = ngram_range
        self.classes = []
        self.class_log_priors = {}
        self.feature_log_probs = {}
        self.vocabulary = set()
        self.vocab_size = 0
        self.class_totals = {}
        self.class_feature_counts = {}
        self.total_docs = 0
        self.trained = False

    def fit(self, X: list, y: list):
        self.classes = list(set(y))
        self.total_docs = len(X)
        class_docs = Counter(y)
        self.class_feature_counts = {c: Counter() for c in self.classes}
        for text, label in zip(X, y):
            self.class_feature_counts[label].update(get_features(text, self.ngram_range))
        for c in self.classes:
            self.vocabulary.update(self.class_feature_counts[c].keys())
        self.vocab_size = len(self.vocabulary)
        self.class_totals = {c: sum(self.class_feature_counts[c].values()) for c in self.classes}
        self.class_log_priors = {c: math.log(class_docs[c] / self.total_docs) for c in self.classes}
        self.feature_log_probs = {}
        for c in self.classes:
            denom = self.class_totals[c] + self.vocab_size
            self.feature_log_probs[c] = {
                feat: math.log((self.class_feature_counts[c].get(feat, 0) + 1) / denom)
                for feat in self.vocabulary
            }
        self.trained = True
        return self

    def predict_proba(self, text: str) -> dict:
        if not self.trained:
            raise RuntimeError("Model not trained.")
        feats = get_features(text, self.ngram_range)
        scores = {}
        for c in self.classes:
            denom = self.class_totals[c] + self.vocab_size
            log_score = self.class_log_priors[c]
            for feat, count in feats.items():
                if feat in self.feature_log_probs[c]:
                    log_score += count * self.feature_log_probs[c][feat]
                else:
                    log_score += count * math.log(1 / denom)
            scores[c] = log_score
        max_s = max(scores.values())
        exp_s = {c: math.exp(s - max_s) for c, s in scores.items()}
        total = sum(exp_s.values())
        return {c: v / total for c, v in exp_s.items()}

    def predict(self, text: str) -> tuple:
        proba = self.predict_proba(text)
        best = max(proba, key=proba.get)
        return best, proba[best]

    def get_top_features(self, text: str, top_n=5) -> list:
        feats = get_features(text, self.ngram_range)
        intent, _ = self.predict(text)
        others = [c for c in self.classes if c != intent]
        scored = []
        for feat, count in feats.items():
            if feat not in self.feature_log_probs.get(intent, {}):
                continue
            si = self.feature_log_probs[intent][feat]
            avg_o = sum(self.feature_log_probs[c].get(feat, math.log(1e-10)) for c in others) / max(len(others), 1)
            scored.append((feat.replace("_", " "), (si - avg_o) * count))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [f for f, _ in scored[:top_n]]

    def perplexity(self, texts: list, labels: list) -> float:
        if not self.trained or not texts:
            return float("inf")
        total_lp, total_n = 0.0, 0
        for text, label in zip(texts, labels):
            feats = get_features(text, self.ngram_range)
            n = sum(feats.values())
            denom = self.class_totals.get(label, 1) + self.vocab_size
            for feat, count in feats.items():
                lp = self.feature_log_probs.get(label, {}).get(feat, math.log(1 / denom))
                total_lp += count * lp
            total_n += n
        return math.exp(-total_lp / max(total_n, 1))

    def save(self, path=MODEL_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path=MODEL_PATH):
        with open(path, "rb") as f:
            return pickle.load(f)


TRAINING_DATA = [
    ("what is the price of apartment in ariana", "price_estimation"),
    ("quel est le prix d un appartement a tunis", "price_estimation"),
    ("combien coute une villa a sfax", "price_estimation"),
    ("prix maison location sousse", "price_estimation"),
    ("estimation prix appartement s2 ariana", "price_estimation"),
    ("how much does a studio cost in hammamet", "price_estimation"),
    ("average price property nabeul", "price_estimation"),
    ("prix vente appartement centre ville tunis", "price_estimation"),
    ("quel prix pour un s plus 3 a sfax", "price_estimation"),
    ("cost studio rent monastir", "price_estimation"),
    ("prix appartement 3 chambres ariana", "price_estimation"),
    ("combien vaut une maison manouba", "price_estimation"),
    ("what is the rent for 2 bedroom in sousse", "price_estimation"),
    ("prix villa piscine hammamet", "price_estimation"),
    ("tarif location studio tunis", "price_estimation"),
    ("price apartment 100m2 sfax", "price_estimation"),
    ("estimation maison 200 metres carres", "price_estimation"),
    ("prix moyen m2 ariana", "price_estimation"),
    ("valeur bien immobilier bizerte", "price_estimation"),
    ("cout location appartement gabes", "price_estimation"),
    ("is this a good investment in sfax", "investment_analysis"),
    ("best areas to invest in tunis", "investment_analysis"),
    ("rental yield ariana apartment", "investment_analysis"),
    ("investment opportunity real estate tunisia", "investment_analysis"),
    ("rentabilite investissement immobilier sousse", "investment_analysis"),
    ("meilleur quartier investir tunis", "investment_analysis"),
    ("return on investment property sfax", "investment_analysis"),
    ("analyse investissement immobilier ariana", "investment_analysis"),
    ("opportunite investissement villa hammamet", "investment_analysis"),
    ("rendement locatif appartement monastir", "investment_analysis"),
    ("worth investing nabeul real estate", "investment_analysis"),
    ("investissement rentable tunisie", "investment_analysis"),
    ("best neighborhood ariana to live", "location_analysis"),
    ("meilleur quartier sfax centre", "location_analysis"),
    ("proche ecole transport tunis", "location_analysis"),
    ("analyse spatiale marche immobilier tunis", "location_analysis"),
    ("quartier calme proche mer hammamet", "location_analysis"),
    ("overview real estate market sousse", "location_analysis"),
    ("market analysis property monastir", "location_analysis"),
    ("statistiques marche immobilier tunisie", "location_analysis"),
    ("quartier residence ville sfax", "location_analysis"),
    ("map properties near center ariana", "location_analysis"),
    ("is this property legally compliant", "legal_verification"),
    ("verification conformite legale bien", "legal_verification"),
    ("titre foncier appartement valide", "legal_verification"),
    ("legal status property tunis", "legal_verification"),
    ("documents requis achat immobilier tunisie", "legal_verification"),
    ("verification juridique propriete", "legal_verification"),
    ("check legal compliance villa", "legal_verification"),
    ("conformite urbanisme sfax", "legal_verification"),
    ("permis construire valide", "legal_verification"),
    ("statut legal bien immobilier", "legal_verification"),
    ("generate complete report tunis market", "report_generation"),
    ("generer rapport complet marche immobilier", "report_generation"),
    ("rapport analyse prix sfax", "report_generation"),
    ("create pdf report property analysis", "report_generation"),
    ("generer document bilan immobilier", "report_generation"),
    ("export rapport investissement ariana", "report_generation"),
    ("produce market report sousse", "report_generation"),
    ("rapport statistique marche tunisie", "report_generation"),
    ("overview marche immobilier tunisien", "general_query"),
    ("information general immobilier tunisie", "general_query"),
    ("comment fonctionne estate mind", "general_query"),
    ("help me understand real estate tunisia", "general_query"),
    ("quelles sont les villes disponibles", "general_query"),
    ("what cities are covered", "general_query"),
    ("aide moi a trouver bien immobilier", "general_query"),
    ("bonjour je cherche information", "general_query"),
    ("hello what can you do", "general_query"),
    ("informations generales tunisie immobilier", "general_query"),
]

_model = None

def get_classifier() -> NaiveBayesClassifier:
    global _model
    if _model is not None:
        return _model
    if os.path.exists(MODEL_PATH):
        try:
            _model = NaiveBayesClassifier.load(MODEL_PATH)
            return _model
        except Exception:
            pass
    _model = NaiveBayesClassifier(ngram_range=(1, 3))
    _model.fit([t for t, _ in TRAINING_DATA], [l for _, l in TRAINING_DATA])
    return _model
