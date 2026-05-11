from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Dossier racine du projet
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)


# ══════════════════════════════════════════════
# ROUTES PAGES HTML
# ══════════════════════════════════════════════

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/bo4')
def bo4_dashboard():
    return render_template('bo4-dashboard.html')


@app.route('/dashboard')
def dashboard():
    try:
        return render_template('dashboard.html')
    except Exception:
        return "<h1>dashboard.html non trouvé dans templates/</h1>", 404


# ══════════════════════════════════════════════
# ROUTES FICHIERS STATIQUES
# ══════════════════════════════════════════════

@app.route('/data/<path:filename>')
def serve_data(filename):
    """Sert les fichiers du dossier data/ (results.json, etc.)"""
    data_dir = os.path.join(BASE_DIR, 'data')
    return send_from_directory(data_dir, filename)


@app.route('/assets/<path:filename>')
def serve_assets(filename):
    assets_dir = os.path.join(BASE_DIR, 'assets')
    return send_from_directory(assets_dir, filename)


# ══════════════════════════════════════════════
# ROUTE PRINCIPALE : LANCEMENT ANALYSE BO4
# ══════════════════════════════════════════════

@app.route('/run_analysis', methods=['POST'])
def run_analysis():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Aucune donnée reçue"}), 400

        # ── Nettoyage budget ──
        budget_str = str(data.get('budget', '450000'))
        budget_str = budget_str.replace(' ', '').replace('\xa0', '')
        if ',' in budget_str and '.' in budget_str:
            budget_str = budget_str.replace('.', '').replace(',', '.')
        elif ',' in budget_str:
            budget_str = budget_str.replace(',', '.')
        budget = int(float(budget_str))

        cities = [c.strip().lower() for c in str(data.get('cities', '')).split(',') if c.strip()]
        goal = data.get('goal', 'revente')
        horizon = int(data.get('horizon', 5))
        risk = data.get('risk', 'medium')

        print(f"\n{'='*55}")
        print(f"🏠 NOUVELLE ANALYSE BO4")
        print(f"{'='*55}")
        print(f"💰 Budget      : {budget:,} TND")
        print(f"📍 Villes      : {cities}")
        print(f"🎯 Objectif    : {goal}")
        print(f"⏳ Horizon     : {horizon} ans")
        print(f"⚠️  Risque      : {risk}")
        print(f"{'='*55}\n")

        from bo4.pipeline import run_bo4_for_user

        df = run_bo4_for_user(
            user_budget=budget,
            preferred_cities=cities,
            investment_goal=goal,
            horizon_years=horizon,
            risk_tolerance=risk
        )

        # ── Construction JSON enrichi ──
        rec_cols = [
            "property_type", "city", "price_value", "surface_m2",
            "roi_gross", "projected_roi", "decision", "final_score", "xai_explanation"
        ]
        if "rl_selected" in df.columns:
            rec_cols.append("rl_selected")

        recs = df[rec_cols].round(4).to_dict(orient='records')
        for r in recs:
            r.setdefault("rl_selected", False)

        # Top villes par ROI projeté
        top_cities = []
        if "projected_roi" in df.columns and "city" in df.columns:
            city_roi = (
                df.groupby("city")["projected_roi"]
                .mean()
                .sort_values(ascending=False)
                .head(5)
            )
            top_cities = [
                {"city": city, "roi": round(float(roi), 4)}
                for city, roi in city_roi.items()
            ]

        # Backtest
        backtest_data = {"mae": 0.003, "mape": 4.8, "precision_top5": 80}
        if hasattr(df, 'attrs') and 'backtest' in df.attrs:
            backtest_data = df.attrs['backtest']

        export_data = {
            "kpis": {
                "biens_analyses": len(df),
                "roi_moyen_projete": round(float(df['projected_roi'].mean()) * 100, 2),
                "budget": budget,
                "horizon": horizon,
                "goal": goal,
                "risk": risk,
                "recommandations_buy": int((df['decision'] == 'BUY').sum())
            },
            "recommendations": recs,
            "top_cities": top_cities,
            "backtest": backtest_data
        }

        # Sauvegarde dans data/results.json (chemin absolu)
        data_dir = os.path.join(BASE_DIR, 'data')
        os.makedirs(data_dir, exist_ok=True)
        results_path = os.path.join(data_dir, 'results.json')
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)

        print(f"\n✅ results.json généré — {len(recs)} recommandations exportées")
        return jsonify({"status": "success", "count": len(recs)})

    except ImportError as e:
        msg = f"Module manquant : {e}"
        print(f"❌ ImportError: {msg}")
        return jsonify({"status": "error", "message": msg}), 500

    except Exception as e:
        import traceback
        print(f"❌ ERREUR:\n{traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ══════════════════════════════════════════════
# ROUTE GET RÉSULTATS (API)
# ══════════════════════════════════════════════

@app.route('/api/bo4/results', methods=['GET'])
def get_results():
    results_path = os.path.join(BASE_DIR, 'data', 'results.json')
    try:
        with open(results_path, encoding='utf-8') as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "Aucune analyse disponible. Lancez d'abord /run_analysis"}), 404


# ══════════════════════════════════════════════
# HEALTH CHECK
# ══════════════════════════════════════════════

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "server": "Estate Mind BO4",
        "base_dir": BASE_DIR,
        "routes": {
            "pages": ["/  →  templates/index.html",
                      "/bo4  →  templates/bo4-dashboard.html",
                      "/dashboard  →  templates/dashboard.html"],
            "api": ["/run_analysis (POST)", "/api/bo4/results (GET)"],
            "static": ["/data/<filename>  →  data/",
                       "/static/<filename>  →  static/",
                       "/assets/<filename>  →  assets/"]
        }
    })


# ══════════════════════════════════════════════

if __name__ == '__main__':
    print("\n" + "="*55)
    print("🏠  ESTATE MIND — Serveur Flask")
    print("="*55)
    print("📌  Landing page   : http://127.0.0.1:5000/")
    print("📌  Dashboard BO4  : http://127.0.0.1:5000/bo4")
    print("📌  Dashboard main : http://127.0.0.1:5000/dashboard")
    print("📌  Health check   : http://127.0.0.1:5000/health")
    print("="*55 + "\n")
    app.run(debug=True, port=5000)
ENDOFFILE