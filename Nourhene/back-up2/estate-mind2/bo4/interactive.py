from bo4.pipeline import run_bo4_for_user

def interactive_mode():
    print("=" * 60)
    print("🏠 ESTATE MIND - Assistant Investissement Immobilier")
    print("=" * 60)
    print("Parle-moi de ton projet d'investissement :\n")

    try:
        # Budget
        budget_input = input("💰 Budget maximum (TND) : ")
        user_budget = float(budget_input.replace(" ", "").replace(",", "")) if budget_input.strip() else 450000

        # Villes préférées
        cities_input = input("📍 Villes préférées (séparées par virgule) : ")
        preferred_cities = [c.strip() for c in cities_input.split(",") if c.strip()]
        if not preferred_cities:
            preferred_cities = ["Tunis", "Sousse", "Hammamet", "La Marsa"]

        # Objectif d'investissement
        goal = input("🎯 Objectif principal (location_longue / airbnb / revente) : ").strip().lower()
        if goal not in ["location_longue", "airbnb", "revente"]:
            goal = "location_longue"

        # Horizon
        horizon_input = input("⏳ Horizon d'investissement (années) : ")
        horizon_years = int(horizon_input) if horizon_input.strip().isdigit() else 5

        # Tolérance au risque
        risk = input("⚠️ Tolérance au risque (low / medium / high) : ").strip().lower()
        if risk not in ["low", "medium", "high"]:
            risk = "medium"
            print("   → Risque par défaut défini sur : medium")

        print("\n🔄 Analyse en cours... Merci de patienter\n")

        # Lancement de l'analyse
        df = run_bo4_for_user(
            user_budget=user_budget,
            preferred_cities=preferred_cities,
            investment_goal=goal,
            horizon_years=horizon_years,
            risk_tolerance=risk
        )

        if df is not None:
            print("\n" + "=" * 60)
            print("✅ Analyse terminée avec succès !")
            print("Tu peux relancer le programme pour tester un autre scénario.")
            print("=" * 60)

    except ValueError as ve:
        print(f"❌ Erreur de saisie : {ve}")
        print("Veuillez entrer des nombres valides pour le budget et l'horizon.")
    except Exception as e:
        print(f"❌ Erreur inattendue : {e}")
        print("Vérifiez que tous les fichiers du dossier 'bo4' sont présents et corrects.")


if __name__ == "__main__":
    interactive_mode()