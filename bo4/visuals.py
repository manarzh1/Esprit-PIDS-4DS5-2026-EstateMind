import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import warnings
import os

warnings.filterwarnings("ignore")

# Style global
plt.rcParams.update({
    "figure.facecolor": "#0f1117",
    "axes.facecolor": "#0f1117",
    "axes.edgecolor": "#2d2d2d",
    "axes.labelcolor": "#e0e0e0",
    "xtick.color": "#a0a0a0",
    "ytick.color": "#a0a0a0",
    "text.color": "#e0e0e0",
    "grid.color": "#1e1e1e",
    "grid.linewidth": 0.8,
    "font.family": "DejaVu Sans",
    "figure.dpi": 120,
})

ACCENT = "#00c8a0"
ACCENT2 = "#f7c59f"
DANGER = "#e05c5c"
MUTED = "#4a4a6a"


def _save_or_show(fig, filename: str = None):
    os.makedirs("outputs", exist_ok=True)
    if filename:
        path = f"outputs/{filename}"
        fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
        print(f"   → Sauvegardé : {path}")
    plt.close(fig)


def plot_roi_by_city(df: pd.DataFrame, save: bool = True):
    """Barplot ROI moyen par ville avec gradient de couleur."""
    city_roi = (
        df.groupby("city")["roi_gross"]
        .mean()
        .sort_values(ascending=False)
        .head(12)
        .reset_index()
    )

    fig, ax = plt.subplots(figsize=(12, 5))
    fig.patch.set_facecolor("#0f1117")

    colors = [ACCENT if i < 3 else MUTED for i in range(len(city_roi))]
    bars = ax.barh(city_roi["city"], city_roi["roi_gross"] * 100, color=colors, height=0.6)

    # Annotations
    for bar, val in zip(bars, city_roi["roi_gross"]):
        ax.text(
            bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
            f"{val*100:.2f}%", va="center", ha="left",
            color="#e0e0e0", fontsize=9
        )

    ax.set_xlabel("ROI Brut Moyen (%)", color="#a0a0a0")
    ax.set_title("📍 ROI Moyen par Ville", color="#ffffff", fontsize=14, pad=15)
    ax.invert_yaxis()
    ax.axvline(df["roi_gross"].mean() * 100, color=ACCENT2, linestyle="--", linewidth=1.2,
               label=f"Moyenne: {df['roi_gross'].mean()*100:.2f}%")
    ax.legend(loc="lower right", framealpha=0.2)
    ax.grid(axis="x", alpha=0.3)

    _save_or_show(fig, "roi_by_city.png" if save else None)
    return fig


def plot_price_distribution(df: pd.DataFrame, save: bool = True):
    """Histogramme distribution des prix avec KDE."""
    fig, ax = plt.subplots(figsize=(11, 5))
    fig.patch.set_facecolor("#0f1117")

    data = df["price_value"].dropna()
    data_clip = data[data < data.quantile(0.97)]

    ax.hist(data_clip / 1000, bins=60, color=MUTED, alpha=0.7, edgecolor="none")

    # KDE overlay
    from scipy.stats import gaussian_kde
    kde = gaussian_kde(data_clip / 1000)
    x_range = np.linspace(data_clip.min() / 1000, data_clip.max() / 1000, 300)
    kde_vals = kde(x_range)
    ax2 = ax.twinx()
    ax2.plot(x_range, kde_vals, color=ACCENT, linewidth=2)
    ax2.set_yticks([])
    ax2.set_facecolor("#0f1117")

    ax.axvline(data_clip.median() / 1000, color=ACCENT2, linestyle="--", linewidth=1.5,
               label=f"Médiane: {data_clip.median()/1000:.0f}k TND")
    ax.set_xlabel("Prix (milliers TND)", color="#a0a0a0")
    ax.set_ylabel("Nombre de biens", color="#a0a0a0")
    ax.set_title("💰 Distribution des Prix Immobiliers", color="#ffffff", fontsize=14, pad=15)
    ax.legend(framealpha=0.2)
    ax.grid(alpha=0.2)

    _save_or_show(fig, "price_distribution.png" if save else None)
    return fig


def plot_score_vs_roi(df: pd.DataFrame, save: bool = True):
    """Scatter plot: Score final vs ROI projeté, coloré par décision."""
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor("#0f1117")

    color_map = {"BUY": ACCENT, "HOLD": ACCENT2, "AVOID": DANGER}
    for decision, group in df.groupby("decision"):
        ax.scatter(
            group["projected_roi"] * 100,
            group["final_score"],
            c=color_map.get(decision, MUTED),
            alpha=0.65, s=25, label=decision, edgecolors="none"
        )

    ax.set_xlabel("ROI Projeté (%)", color="#a0a0a0")
    ax.set_ylabel("Score Final", color="#a0a0a0")
    ax.set_title("🎯 Score Final vs ROI Projeté", color="#ffffff", fontsize=14, pad=15)
    ax.legend(framealpha=0.2)
    ax.grid(alpha=0.2)

    _save_or_show(fig, "score_vs_roi.png" if save else None)
    return fig


def plot_decision_pie(df: pd.DataFrame, save: bool = True):
    """Camembert des décisions BUY/HOLD/AVOID."""
    counts = df["decision"].value_counts()

    fig, ax = plt.subplots(figsize=(6, 6))
    fig.patch.set_facecolor("#0f1117")

    colors = [{"BUY": ACCENT, "HOLD": ACCENT2, "AVOID": DANGER}.get(d, MUTED) for d in counts.index]
    wedges, texts, autotexts = ax.pie(
        counts.values, labels=counts.index, colors=colors,
        autopct="%1.1f%%", startangle=90,
        wedgeprops={"edgecolor": "#0f1117", "linewidth": 2}
    )
    for t in texts + autotexts:
        t.set_color("#e0e0e0")

    ax.set_title("⚖️ Répartition des Décisions", color="#ffffff", fontsize=14, pad=15)

    _save_or_show(fig, "decision_pie.png" if save else None)
    return fig


def plot_shap_summary(df: pd.DataFrame, save: bool = True):
    """
    Bar chart des importances SHAP moyennes (si colonnes shap_ disponibles).
    Fallback: feature importance classique.
    """
    shap_cols = [c for c in df.columns if c.startswith("shap_")]

    if not shap_cols:
        print("   → Colonnes SHAP non trouvées, skip.")
        return None

    mean_abs_shap = df[shap_cols].abs().mean().sort_values(ascending=True)
    labels = [c.replace("shap_", "").replace("_", " ").title() for c in mean_abs_shap.index]

    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor("#0f1117")

    colors = [ACCENT if v == mean_abs_shap.max() else MUTED for v in mean_abs_shap.values]
    ax.barh(labels, mean_abs_shap.values, color=colors, height=0.6)
    ax.set_xlabel("Importance SHAP Moyenne |valeur|", color="#a0a0a0")
    ax.set_title("🔍 Importance des Features (SHAP)", color="#ffffff", fontsize=14, pad=15)
    ax.grid(axis="x", alpha=0.3)

    _save_or_show(fig, "shap_importance.png" if save else None)
    return fig


def plot_projected_roi_by_city(df: pd.DataFrame, save: bool = True):
    """Comparaison ROI actuel vs projeté par ville."""
    if "projected_roi" not in df.columns:
        return None

    city_data = df.groupby("city").agg(
        roi_gross=("roi_gross", "mean"),
        projected_roi=("projected_roi", "mean")
    ).sort_values("projected_roi", ascending=False).head(10).reset_index()

    x = np.arange(len(city_data))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 5))
    fig.patch.set_facecolor("#0f1117")

    ax.bar(x - width/2, city_data["roi_gross"] * 100, width, label="ROI Actuel", color=MUTED, alpha=0.85)
    ax.bar(x + width/2, city_data["projected_roi"] * 100, width, label="ROI Projeté", color=ACCENT, alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(city_data["city"], rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("ROI (%)", color="#a0a0a0")
    ax.set_title("📈 ROI Actuel vs Projeté par Ville", color="#ffffff", fontsize=14, pad=15)
    ax.legend(framealpha=0.2)
    ax.grid(axis="y", alpha=0.3)

    _save_or_show(fig, "roi_comparison.png" if save else None)
    return fig


def generate_all_visuals(df: pd.DataFrame):
    """Génère tous les visuels en une fois."""
    print("\n📊 Génération des visuels...")
    plot_roi_by_city(df)
    plot_price_distribution(df)
    plot_score_vs_roi(df)
    plot_decision_pie(df)
    plot_shap_summary(df)
    plot_projected_roi_by_city(df)
    print("✅ Visuels sauvegardés dans /outputs/")