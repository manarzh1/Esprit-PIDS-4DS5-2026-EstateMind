#!/usr/bin/env python3
"""
scripts/test_mock_agents.py
============================
Tests des mock agents BO1, BO2, BO3, BO4 en mode direct.
Lance depuis la racine du projet : python scripts/test_mock_agents.py

Resultats attendus :
  BO3 "Prix S+2 Ariana"   → ~240 000 TND, conf ~78%, 397 annonces
  BO4 "Investir Hammamet" → score 9.1/10, rendement 8.9%
  BO1 "Fiabilite Tunis"   → trust ~82%, 6877 annonces
  BO2 "Marche Hammamet"   → ppm2 ~3720, trend +3.3%
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── BO3 ──────────────────────────────────────────────────────────────────────
print("=" * 60)
print("TEST BO3 — estimate_price (S+2 Ariana, 100m²)")
print("=" * 60)
from app.services.agents.bo3_mock_agent import estimate_price, recommend_zones, sarima_invest

res = estimate_price(city="Ariana", surface=100, bedrooms=3, bathrooms=1, budget=0)
est = res["estimation"]
print(f"  Ville résolue   : {res['city_resolved']}")
print(f"  Prix estimé     : {est['predicted']:,} TND")
print(f"  Fourchette      : {est['ci_lower']:,} – {est['ci_upper']:,} TND")
print(f"  Médiane marché  : {est['city_median']:,} TND")
print(f"  Prix/m²         : {est['price_per_m2']:,} TND")
print(f"  Confiance       : {est['confidence']}%")
print(f"  Annonces        : {res['total_listings']}")
assert res['total_listings'] > 0, "FAIL: total_listings == 0"
assert est['confidence'] > 0, "FAIL: confidence == 0"
print("  → PASS\n")

print("=" * 60)
print("TEST BO3 — recommend_zones (Tunis, appartement, 300 000 TND)")
print("=" * 60)
rec = recommend_zones(ville="Tunis", budget=300_000, type_bien="appartement")
print(f"  Ville : {rec['ville']}, {len(rec['zones'])} zones")
for z in rec["zones"][:3]:
    print(f"    {z['zone']:20s} | {z['price']:,} TND | score {z['score']}/100")
assert len(rec["zones"]) > 0, "FAIL: no zones"
print("  → PASS\n")

print("=" * 60)
print("TEST BO3 — sarima_invest (Tunis)")
print("=" * 60)
sarima = sarima_invest(gouvernorat="Tunis")
data = sarima["data"]
print(f"  Gouvernorat     : {data['gouvernorat']}")
print(f"  Valeur actuelle : {data['derniere_valeur']} TND/m²")
print(f"  Prévision       : {data['prevision_finale']} TND/m²")
print(f"  Hausse          : +{data['hausse_pct']}%")
assert data["derniere_valeur"] > 0, "FAIL: no price"
print("  → PASS\n")

# ── BO4 ──────────────────────────────────────────────────────────────────────
print("=" * 60)
print("TEST BO4 — score_investment (Hammamet, 350 000 TND)")
print("=" * 60)
from app.services.agents.bo4_mock_agent import score_investment, compare_cities

sc = score_investment(city="Hammamet", budget=350_000, property_type="appartement")
print(f"  Score           : {sc['investment_score']}/10")
print(f"  Rendement       : {sc['rental_yield']}%")
print(f"  Risque          : {sc['risk_level']}")
print(f"  Recommandation  : {sc['recommendation'][:60]}...")
assert sc["investment_score"] > 0, "FAIL: no score"
print("  → PASS\n")

print("=" * 60)
print("TEST BO4 — compare_cities (Top 5)")
print("=" * 60)
cmp = compare_cities(["Hammamet", "Nabeul", "Tunis", "Sousse", "Sfax"])
for c in cmp["comparison"]:
    print(f"  {c['city']:15s} | {c['investment_score']:.1f}/10 | {c['rental_yield']:.1f}% | {c['risk_level']}")
print("  → PASS\n")

# ── BO1 ──────────────────────────────────────────────────────────────────────
print("=" * 60)
print("TEST BO1 — analyze_listing (Tunis, 300 000 TND, 100m²)")
print("=" * 60)
from app.services.agents.bo1_mock_agent import analyze_listing, get_dashboard, get_listings

dash = get_dashboard()
print(f"  Total annonces  : {dash['total']:,}")
print(f"  Suspect count   : {dash['suspect_count']}")
al = analyze_listing(price=300_000, surface=100, city="Tunis", description="Appartement rénové", source="tayara")
print(f"  Trust score     : {al['trust_score']:.3f}")
print(f"  Trust label     : {al.get('trust_label', al.get('label','N/A'))}")
assert dash["total"] > 0, "FAIL: no listings"
print("  → PASS\n")

# ── BO2 ──────────────────────────────────────────────────────────────────────
print("=" * 60)
print("TEST BO2 — get_forecast (Hammamet)")
print("=" * 60)
from app.services.agents.bo2_mock_agent import get_forecast, get_cluster_city, predict_emerging

fc = get_forecast(city="Hammamet")
print(f"  Prix/m² prévu   : {fc.get('mean_predicted','N/A')} TND")
print(f"  Tendance        : +{fc.get('trend_pct','N/A')}%")
print(f"  Confiance (MAPE): {fc.get('model_mape', fc.get('mape','N/A'))}%")
cl = get_cluster_city(city="Hammamet")
print(f"  Cluster         : {cl.get('cluster_label', cl.get('label','N/A'))}")
em = predict_emerging(city="Hammamet", median_price=3600)
print(f"  Émergence prob  : {em.get('emergence_proba', em.get('emerging_probability', 0))*100:.0f}%")
assert fc["mean_predicted"] > 0, "FAIL: no forecast"
print("  → PASS\n")

print("=" * 60)
print("TOUS LES TESTS PASSENT — Mock agents opérationnels ✓")
print("=" * 60)
