"""scripts/train_classifier.py — Entraine et sauvegarde le modele NB."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.nlp.naive_bayes import NaiveBayesClassifier, TRAINING_DATA, MODEL_PATH, INTENT_LABELS

print("Training Naive Bayes classifier...")
texts  = [t for t, _ in TRAINING_DATA]
labels = [l for _, l in TRAINING_DATA]

clf = NaiveBayesClassifier(ngram_range=(1, 3))
clf.fit(texts, labels)
print(f"  Vocabulary: {clf.vocab_size} features")
print(f"  Classes: {clf.classes}")

# Evaluation rapide
correct = sum(1 for t, l in TRAINING_DATA if clf.predict(t)[0] == l)
print(f"  Training accuracy: {correct}/{len(TRAINING_DATA)} = {correct/len(TRAINING_DATA):.1%}")

# Perplexite
pp = clf.perplexity(texts, labels)
print(f"  Perplexity: {pp:.2f}")

clf.save(MODEL_PATH)
print(f"  Saved to: {MODEL_PATH}")
print("Done!")
