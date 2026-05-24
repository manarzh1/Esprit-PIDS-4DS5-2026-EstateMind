"""scripts/evaluate.py — Evaluation complete du pipeline NLP."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.evaluation.evaluator import evaluate_classifier
from app.services.nlp.naive_bayes import INTENT_LABELS
import json

print("=" * 55)
print("  ESTATE MIND — Evaluation du Classifieur NB")
print("=" * 55)

result = evaluate_classifier()
print(f"\n  Accuracy      : {result['accuracy']:.1%}")
print(f"  Macro F1      : {result['macro_f1']:.4f}")
print(f"  Perplexite    : {result['perplexity']:.2f}")
print(f"  ECE           : {result['ece']:.4f}")
print(f"  Vocab size    : {result['vocabulary_size']}")
print(f"  Train examples: {result['total_training_examples']}")
print(f"  Hallucination : {result['hallucination_rate']:.0%}")
print(f"\n  Per-class metrics:")
for c in result["per_class"]:
    print(f"    {c['intent']:<25} P={c['precision']:.3f} R={c['recall']:.3f} F1={c['f1']:.3f} (n={c['support']})")

print("\n  Test queries:")
from app.services.nlp.naive_bayes import get_classifier
clf = get_classifier()
tests = [
    ("quel est le prix d'un S+2 a Ariana ?", "price_estimation"),
    ("is this a good investment in sfax?", "investment_analysis"),
    ("meilleur quartier tunis", "location_analysis"),
    ("verification conformite legale", "legal_verification"),
    ("generer rapport complet", "report_generation"),
    ("bonjour que faites vous", "general_query"),
]
for query, expected in tests:
    pred, conf = clf.predict(query)
    ok = "✅" if pred == expected else "❌"
    print(f"  {ok} [{conf:.0%}] {query[:45]:<45} → {pred}")

print("=" * 55)
