"""tests/test_nlp_pipeline.py — Tests du pipeline NLP."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.nlp.naive_bayes import get_classifier, TRAINING_DATA, INTENT_LABELS
from app.services.nlp.tunisian_normalizer import TunisianNormalizer
from app.services.nlp.language_detector import detect_language
from app.services.nlp.intent_detector import detect_intent

def test_naive_bayes_training():
    clf = get_classifier()
    assert clf.trained
    assert clf.vocab_size > 0
    assert len(clf.classes) == 6

def test_intent_detection_fr():
    clf = get_classifier()
    pred, conf = clf.predict("quel est le prix d un appartement a ariana")
    assert pred == "price_estimation"
    assert conf > 0.5

def test_intent_detection_en():
    clf = get_classifier()
    pred, conf = clf.predict("is this a good investment in sfax")
    assert pred == "investment_analysis"

def test_intent_detection_legal():
    clf = get_classifier()
    pred, conf = clf.predict("is this property legally compliant")
    assert pred == "legal_verification"

def test_darija_normalization():
    n = TunisianNormalizer()
    r = n.normalize("chnowa soum dar fi tunis")
    assert r.is_tunisian
    assert len(r.words_replaced) > 0
    assert "prix" in r.normalized_text or "maison" in r.normalized_text

def test_language_detection_fr():
    r = detect_language("quel est le prix de l appartement")
    assert r["language"] == "fr"
    assert r["confidence"] > 0.5

def test_language_detection_ar():
    r = detect_language("ما هو سعر الشقة في سوسة")
    assert r["language"] == "ar"

def test_language_detection_en():
    r = detect_language("what is the price of the apartment")
    assert r["language"] == "en"

def test_top_ngrams():
    clf = get_classifier()
    ngrams = clf.get_top_features("price apartment ariana")
    assert isinstance(ngrams, list)
    assert len(ngrams) > 0

def test_perplexity():
    clf = get_classifier()
    texts = [t for t, _ in TRAINING_DATA[:10]]
    labels = [l for _, l in TRAINING_DATA[:10]]
    pp = clf.perplexity(texts, labels)
    assert pp > 0
    assert pp != float("inf")

if __name__ == "__main__":
    tests = [
        test_naive_bayes_training,
        test_intent_detection_fr,
        test_intent_detection_en,
        test_intent_detection_legal,
        test_darija_normalization,
        test_language_detection_fr,
        test_language_detection_ar,
        test_language_detection_en,
        test_top_ngrams,
        test_perplexity,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")
