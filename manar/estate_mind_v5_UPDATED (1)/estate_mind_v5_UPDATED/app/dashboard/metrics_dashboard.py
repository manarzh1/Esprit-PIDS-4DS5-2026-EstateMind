"""
app/dashboard/metrics_dashboard.py
=====================================
Dashboard Dash/Plotly — Theme Orange/Noir.
http://localhost:8050
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.evaluation.evaluator import evaluate_classifier
from app.services.nlp.naive_bayes import INTENT_LABELS

try:
    import dash
    from dash import dcc, html, Input, Output
    import plotly.graph_objects as go
    import plotly.express as px
except ImportError:
    print("Install dash: pip install dash plotly")
    sys.exit(1)

# Theme
BG = "#0A0A0A"; CARD_BG = "#1A1A1A"; ORANGE = "#FF6B00"; WHITE = "#FFFFFF"; GRAY = "#888888"; BORDER = "#2A2A2A"

eval_data = evaluate_classifier()
LABELS_SHORT = [l.replace("_", " ").title() for l in INTENT_LABELS]

app = dash.Dash(__name__, title="Estate Mind — Metrics Dashboard")
app.layout = html.Div(style={"backgroundColor": BG, "minHeight": "100vh", "fontFamily": "Inter, sans-serif", "color": WHITE, "padding": "20px"}, children=[
    # Header
    html.Div([
        html.H1("🏠 Estate Mind — Métriques NLP", style={"color": ORANGE, "margin": "0 0 4px 0", "fontSize": "28px"}),
        html.P("Dashboard de performance du pipeline BO6 — NB Classifier", style={"color": GRAY, "margin": "0"}),
    ], style={"borderBottom": f"2px solid {ORANGE}", "paddingBottom": "16px", "marginBottom": "24px"}),

    # KPI Cards
    html.Div([
        *[html.Div([
            html.Div(label, style={"color": GRAY, "fontSize": "12px", "marginBottom": "4px"}),
            html.Div(value, style={"color": ORANGE, "fontSize": "28px", "fontWeight": "bold"}),
        ], style={"backgroundColor": CARD_BG, "border": f"1px solid {BORDER}", "borderRadius": "8px",
                  "padding": "16px", "flex": "1", "textAlign": "center"})
        for label, value in [
            ("Accuracy", f"{eval_data['accuracy']:.1%}"),
            ("Macro F1", f"{eval_data['macro_f1']:.3f}"),
            ("Perplexité", f"{eval_data['perplexity']:.1f}"),
            ("Vocab Size", f"{eval_data['vocabulary_size']:,}"),
        ]]
    ], style={"display": "flex", "gap": "16px", "marginBottom": "24px"}),

    # Row 1: Confusion Matrix + Per-class F1
    html.Div([
        html.Div([
            html.H3("Matrice de Confusion", style={"color": ORANGE, "fontSize": "16px", "marginBottom": "12px"}),
            dcc.Graph(id="confusion-matrix", config={"displayModeBar": False},
                figure=go.Figure(go.Heatmap(
                    z=eval_data["confusion_matrix"], x=LABELS_SHORT, y=LABELS_SHORT,
                    colorscale=[[0, BG], [0.5, "#8B3000"], [1, ORANGE]],
                    showscale=True, text=eval_data["confusion_matrix"],
                    texttemplate="%{text}", textfont={"color": WHITE},
                )).update_layout(
                    paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG, font_color=WHITE,
                    margin=dict(l=10, r=10, t=10, b=10), height=280,
                    xaxis=dict(tickfont=dict(size=9)), yaxis=dict(tickfont=dict(size=9)),
                )),
        ], style={"flex": "1", "backgroundColor": CARD_BG, "border": f"1px solid {BORDER}", "borderRadius": "8px", "padding": "16px"}),

        html.Div([
            html.H3("F1 par Intention", style={"color": ORANGE, "fontSize": "16px", "marginBottom": "12px"}),
            dcc.Graph(id="f1-chart", config={"displayModeBar": False},
                figure=go.Figure([
                    go.Bar(name="Précision", x=LABELS_SHORT, y=[c["precision"] for c in eval_data["per_class"]], marker_color="#FF8C00"),
                    go.Bar(name="Rappel", x=LABELS_SHORT, y=[c["recall"] for c in eval_data["per_class"]], marker_color=GRAY),
                    go.Bar(name="F1", x=LABELS_SHORT, y=[c["f1"] for c in eval_data["per_class"]], marker_color=ORANGE),
                ]).update_layout(
                    barmode="group", paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
                    font_color=WHITE, margin=dict(l=10, r=10, t=10, b=10), height=280,
                    legend=dict(bgcolor=CARD_BG), xaxis=dict(tickfont=dict(size=9)),
                )),
        ], style={"flex": "1", "backgroundColor": CARD_BG, "border": f"1px solid {BORDER}", "borderRadius": "8px", "padding": "16px"}),
    ], style={"display": "flex", "gap": "16px", "marginBottom": "24px"}),

    # Row 2: Distribution + Pipeline Latency
    html.Div([
        html.Div([
            html.H3("Distribution des Intentions", style={"color": ORANGE, "fontSize": "16px", "marginBottom": "12px"}),
            dcc.Graph(id="pie-chart", config={"displayModeBar": False},
                figure=go.Figure(go.Pie(
                    labels=LABELS_SHORT,
                    values=[c["support"] for c in eval_data["per_class"]],
                    marker=dict(colors=[ORANGE, "#FF8C00", "#CC5500", "#993D00", "#662900", "#331400"]),
                    hole=0.4,
                )).update_layout(
                    paper_bgcolor=CARD_BG, font_color=WHITE,
                    margin=dict(l=10, r=10, t=10, b=10), height=260,
                    legend=dict(bgcolor=CARD_BG, font=dict(size=10)),
                )),
        ], style={"flex": "1", "backgroundColor": CARD_BG, "border": f"1px solid {BORDER}", "borderRadius": "8px", "padding": "16px"}),

        html.Div([
            html.H3("Latence Budget Pipeline (cible)", style={"color": ORANGE, "fontSize": "16px", "marginBottom": "12px"}),
            dcc.Graph(id="latency-chart", config={"displayModeBar": False},
                figure=go.Figure(go.Bar(
                    y=["Étape 1 Langue", "Étape 2 Darija", "Étape 3 Traduction",
                       "Étape 4 NB Class.", "Étape 5 Routage", "Étape 6 Agent HTTP",
                       "Étape 7 Template", "Étape 8 Sauvegarde"],
                    x=[100, 100, 3000, 100, 100, 15000, 100, 500],
                    orientation="h",
                    marker_color=[ORANGE]*8,
                    text=["0.1s","0.1s","3.0s","0.1s","0.1s","15.0s","0.1s","0.5s"],
                    textposition="inside", textfont=dict(color=BG),
                )).update_layout(
                    paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG, font_color=WHITE,
                    margin=dict(l=10, r=10, t=10, b=10), height=260,
                    xaxis=dict(title="ms (log)", type="log"),
                )),
        ], style={"flex": "1", "backgroundColor": CARD_BG, "border": f"1px solid {BORDER}", "borderRadius": "8px", "padding": "16px"}),
    ], style={"display": "flex", "gap": "16px", "marginBottom": "24px"}),

    # Tableau per-class
    html.Div([
        html.H3("Détail par Classe", style={"color": ORANGE, "fontSize": "16px", "marginBottom": "12px"}),
        html.Table([
            html.Thead(html.Tr([html.Th(h, style={"color": ORANGE, "padding": "8px 12px", "borderBottom": f"2px solid {ORANGE}", "textAlign": "left"})
                                for h in ["Intention", "Précision", "Rappel", "F1", "Support"]])),
            html.Tbody([
                html.Tr([
                    html.Td(c["intent"], style={"padding": "6px 12px", "color": WHITE}),
                    html.Td(f"{c['precision']:.3f}", style={"padding": "6px 12px", "color": ORANGE if c['precision'] > 0.9 else WHITE}),
                    html.Td(f"{c['recall']:.3f}", style={"padding": "6px 12px", "color": ORANGE if c['recall'] > 0.9 else WHITE}),
                    html.Td(f"{c['f1']:.3f}", style={"padding": "6px 12px", "fontWeight": "bold", "color": ORANGE}),
                    html.Td(str(c["support"]), style={"padding": "6px 12px", "color": GRAY}),
                ], style={"backgroundColor": CARD_BG if i % 2 == 0 else "#141414"})
                for i, c in enumerate(eval_data["per_class"])
            ])
        ], style={"width": "100%", "borderCollapse": "collapse"}),
    ], style={"backgroundColor": CARD_BG, "border": f"1px solid {BORDER}", "borderRadius": "8px", "padding": "16px"}),

    html.Div([
        html.P("© 2025 Estate Mind — BO6 Orchestrateur | Aucun LLM | Taux hallucination : 0%",
               style={"color": GRAY, "fontSize": "11px", "textAlign": "center", "marginTop": "24px"})
    ])
])

if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "8050"))
    print(f"Dashboard: http://localhost:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)
