"use client";
/**
 * Estate Mind — XAIMarketPanel.tsx
 * ==================================
 * Panneau XAI BO2 pour expliquer les prix et prévisions.
 * À utiliser dans /marche et /territoire.
 *
 * Usage :
 *   <XAIMarketPanel city="Tunis" />
 *   <XAIEmergencePanel city="Nabeul" medianPrice={3200} volume={45} />
 */

import { useState, useEffect } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────
interface ForecastXAI {
  city:              string;
  trend_label:       "hausse" | "stable" | "baisse";
  trend_pct:         number;
  avg_predicted:     number;
  avg_interval_pct:  number;
  mape:              number | null;
  vs_national_pct:   number;
  national_median:   number;
  milestones:        { j30: any; j60: any; j90: any };
  factors:           { factor: string; detail: string; impact: string }[];
  summary:           string;
}

interface EmergenceXAI {
  city:                string;
  emergence_proba_pct: number;
  verdict:             string;
  verdict_color:       string;
  recommendation:      string;
  factors:             { factor: string; detail: string; impact: string }[];
  shap_contributions:  { label: string; magnitude: number; impact: string }[];
  summary:             string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function bold(text: string) {
  const parts = text.split(/\*\*(.*?)\*\*/g);
  return parts.map((p, i) =>
    i % 2 === 1
      ? <strong key={i} style={{ color: "#C8A96E" }}>{p}</strong>
      : <span key={i}>{p}</span>
  );
}

const impactColor = (impact: string) =>
  impact === "positive" ? "#22C55E" : impact === "negative" ? "#EF4444" : "#94A3B8";

const impactBg = (impact: string) =>
  impact === "positive" ? "rgba(22,163,74,0.08)"
  : impact === "negative" ? "rgba(239,68,68,0.08)" : "rgba(255,255,255,0.04)";

// ── Panneau Forecast XAI ──────────────────────────────────────────────────────
export function XAIMarketPanel({ city }: { city: string }) {
  const [data,    setData]    = useState<ForecastXAI | null>(null);
  const [loading, setLoading] = useState(false);
  const [open,    setOpen]    = useState(false);

  const load = async () => {
    if (data) { setOpen(!open); return; }
    setLoading(true);
    setOpen(true);
    try {
      const r = await fetch(`${API}/api/xai/forecast/${encodeURIComponent(city)}`);
      if (r.ok) setData(await r.json());
    } catch {}
    setLoading(false);
  };

  const trendColor =
    data?.trend_label === "hausse" ? "#22C55E"
    : data?.trend_label === "baisse"  ? "#EF4444" : "#94A3B8";
  const trendIcon  =
    data?.trend_label === "hausse" ? "📈" : data?.trend_label === "baisse" ? "📉" : "➡️";

  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={load}
        style={{
          display: "flex", alignItems: "center", gap: 6,
          padding: "6px 12px", borderRadius: 8, cursor: "pointer",
          background: "rgba(200,169,110,0.06)",
          border: "1px solid rgba(200,169,110,0.25)",
          color: "#C8A96E", fontSize: 12, fontWeight: 500,
          fontFamily: "inherit", width: "100%",
          justifyContent: "center",
        }}
      >
        🔍 Expliquer la prévision de prix — {city}
      </button>

      {open && (
        <div style={{
          marginTop: 8, borderRadius: 12, overflow: "hidden",
          border: "1px solid rgba(200,169,110,0.2)",
          background: "rgba(9,9,11,0.95)",
        }}>
          {/* Header */}
          <div style={{
            padding: "12px 16px",
            background: "linear-gradient(135deg, #0D2B52, #1E4D8C)",
            display: "flex", alignItems: "center", justifyContent: "space-between",
          }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "white" }}>
                XAI — Prévision de prix · {city}
              </div>
              <div style={{ fontSize: 11, color: "rgba(255,255,255,0.6)", marginTop: 2 }}>
                Modèle Prophet M4 · BO2
              </div>
            </div>
            {data && (
              <span style={{
                fontSize: 18, fontWeight: 800, color: trendColor,
              }}>
                {trendIcon} {data.trend_pct > 0 ? "+" : ""}{data.trend_pct.toFixed(1)}%
              </span>
            )}
          </div>

          {/* Body */}
          <div style={{ padding: "14px 16px" }}>
            {loading && (
              <div style={{ textAlign: "center", padding: "20px 0", color: "#64748B", fontSize: 13 }}>
                Calcul des explications...
              </div>
            )}

            {data && !loading && (
              <>
                {/* Résumé */}
                <div style={{
                  padding: "10px 12px", borderRadius: 8, marginBottom: 12,
                  background: "rgba(30,77,140,0.15)", border: "1px solid rgba(30,77,140,0.3)",
                  fontSize: 12, lineHeight: 1.6, color: "rgba(255,255,255,0.85)",
                }}>
                  {bold(data.summary)}
                </div>

                {/* KPIs */}
                <div style={{
                  display: "grid", gridTemplateColumns: "1fr 1fr 1fr",
                  gap: 8, marginBottom: 12,
                }}>
                  {[
                    { label: "Prix moyen prévu",     val: `${data.avg_predicted.toLocaleString("fr-FR")} TND/m²` },
                    { label: "Incertitude",           val: `±${data.avg_interval_pct.toFixed(0)}%` },
                    { label: "vs Médiane nationale",  val: `${data.vs_national_pct > 0 ? "+" : ""}${((data.vs_national_pct - 1) * 100).toFixed(1)}%` },
                  ].map(({ label, val }) => (
                    <div key={label} style={{
                      padding: "8px 10px", borderRadius: 8, textAlign: "center",
                      background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
                    }}>
                      <div style={{ fontSize: 11, color: "#64748B", marginBottom: 4 }}>{label}</div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: "#C8A96E" }}>{val}</div>
                    </div>
                  ))}
                </div>

                {/* Jalons */}
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 11, color: "#64748B", marginBottom: 6, fontWeight: 600, textTransform: "uppercase" }}>
                    Jalons de prévision
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6 }}>
                    {Object.entries(data.milestones).map(([key, m]: [string, any]) => (
                      <div key={key} style={{
                        padding: "8px", borderRadius: 8, textAlign: "center",
                        background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
                      }}>
                        <div style={{ fontSize: 10, color: "#64748B", marginBottom: 3 }}>
                          {key === "j30" ? "30 jours" : key === "j60" ? "60 jours" : "90 jours"}
                        </div>
                        <div style={{ fontSize: 14, fontWeight: 700, color: "white" }}>
                          {m.predicted.toLocaleString("fr-FR")}
                        </div>
                        <div style={{ fontSize: 9, color: "#64748B", marginTop: 2 }}>
                          [{m.lower_80.toLocaleString()}–{m.upper_80.toLocaleString()}]
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Facteurs */}
                <div>
                  <div style={{ fontSize: 11, color: "#64748B", marginBottom: 6, fontWeight: 600, textTransform: "uppercase" }}>
                    Facteurs explicatifs
                  </div>
                  {data.factors.map((f, i) => (
                    <div key={i} style={{
                      padding: "8px 10px", borderRadius: 8, marginBottom: 6,
                      background: impactBg(f.impact),
                      border: `1px solid ${impactColor(f.impact)}22`,
                    }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: impactColor(f.impact), marginBottom: 3 }}>
                        {f.impact === "positive" ? "✅" : f.impact === "negative" ? "⚠️" : "ℹ️"} {f.factor}
                      </div>
                      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.6)", lineHeight: 1.5 }}>
                        {f.detail}
                      </div>
                    </div>
                  ))}
                </div>

                {data.mape !== null && (
                  <div style={{
                    marginTop: 8, padding: "6px 10px", borderRadius: 6,
                    background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.2)",
                    fontSize: 11, color: "#FBD24D",
                  }}>
                    ⚠ MAPE = {data.mape}% — {data.mape < 15 ? "Précision satisfaisante" : "Valeur illustrative (peu de données historiques)"}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Panneau Emergence XAI ─────────────────────────────────────────────────────
export function XAIEmergencePanel({
  city, medianPrice, volume,
}: { city: string; medianPrice: number; volume: number }) {
  const [data,    setData]    = useState<EmergenceXAI | null>(null);
  const [loading, setLoading] = useState(false);
  const [open,    setOpen]    = useState(false);

  const load = async () => {
    if (data) { setOpen(!open); return; }
    setLoading(true);
    setOpen(true);
    try {
      const r = await fetch(`${API}/api/xai/emergence`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city, median_price: medianPrice, volume }),
      });
      if (r.ok) setData(await r.json());
    } catch {}
    setLoading(false);
  };

  const verdictColor =
    data?.verdict_color === "green"  ? "#22C55E"
    : data?.verdict_color === "orange" ? "#F97316" : "#94A3B8";

  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={load}
        style={{
          display: "flex", alignItems: "center", gap: 6,
          padding: "6px 12px", borderRadius: 8, cursor: "pointer",
          background: "rgba(200,169,110,0.06)",
          border: "1px solid rgba(200,169,110,0.25)",
          color: "#C8A96E", fontSize: 12, fontWeight: 500,
          fontFamily: "inherit", width: "100%",
          justifyContent: "center",
        }}
      >
        🚀 Analyser le potentiel d'émergence — {city}
      </button>

      {open && (
        <div style={{
          marginTop: 8, borderRadius: 12, overflow: "hidden",
          border: "1px solid rgba(200,169,110,0.2)",
          background: "rgba(9,9,11,0.95)",
        }}>
          {/* Header */}
          <div style={{
            padding: "12px 16px",
            background: "linear-gradient(135deg, #145A32, #1D9E75)",
            display: "flex", alignItems: "center", justifyContent: "space-between",
          }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "white" }}>
                XAI — Analyse d'émergence · {city}
              </div>
              <div style={{ fontSize: 11, color: "rgba(255,255,255,0.6)", marginTop: 2 }}>
                Modèle XGBoost M6 · BO2
              </div>
            </div>
            {data && (
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: verdictColor }}>
                  {data.emergence_proba_pct.toFixed(0)}%
                </div>
                <div style={{ fontSize: 10, color: "rgba(255,255,255,0.5)" }}>prob. émergence</div>
              </div>
            )}
          </div>

          {/* Body */}
          <div style={{ padding: "14px 16px" }}>
            {loading && (
              <div style={{ textAlign: "center", padding: "20px 0", color: "#64748B", fontSize: 13 }}>
                Calcul des explications...
              </div>
            )}

            {data && !loading && (
              <>
                {/* Résumé */}
                <div style={{
                  padding: "10px 12px", borderRadius: 8, marginBottom: 12,
                  background: `${verdictColor}11`, border: `1px solid ${verdictColor}33`,
                  fontSize: 12, lineHeight: 1.6, color: "rgba(255,255,255,0.85)",
                }}>
                  {bold(data.summary)}
                </div>

                {/* Verdict badge */}
                <div style={{
                  display: "inline-flex", alignItems: "center", gap: 8,
                  padding: "6px 14px", borderRadius: 99, marginBottom: 12,
                  background: `${verdictColor}18`,
                  border: `1px solid ${verdictColor}44`,
                }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: verdictColor, display: "inline-block" }} />
                  <span style={{ fontSize: 12, fontWeight: 600, color: verdictColor }}>{data.verdict}</span>
                </div>

                {/* Recommandation */}
                <div style={{
                  padding: "8px 12px", borderRadius: 8, marginBottom: 12,
                  background: "rgba(200,169,110,0.06)", border: "1px solid rgba(200,169,110,0.2)",
                  fontSize: 12, color: "#C8A96E",
                }}>
                  💡 {data.recommendation}
                </div>

                {/* Facteurs */}
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 11, color: "#64748B", marginBottom: 6, fontWeight: 600, textTransform: "uppercase" }}>
                    Facteurs d'émergence
                  </div>
                  {data.factors.map((f, i) => (
                    <div key={i} style={{
                      padding: "8px 10px", borderRadius: 8, marginBottom: 6,
                      background: impactBg(f.impact),
                      border: `1px solid ${impactColor(f.impact)}22`,
                    }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: impactColor(f.impact), marginBottom: 3 }}>
                        {f.impact === "positive" ? "✅" : f.impact === "negative" ? "⚠️" : "ℹ️"} {f.factor}
                      </div>
                      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.6)", lineHeight: 1.5 }}>{f.detail}</div>
                    </div>
                  ))}
                </div>

                {/* SHAP contributions */}
                {data.shap_contributions.length > 0 && (
                  <div>
                    <div style={{ fontSize: 11, color: "#64748B", marginBottom: 6, fontWeight: 600, textTransform: "uppercase" }}>
                      Importance des variables (SHAP)
                    </div>
                    {data.shap_contributions.map((c, i) => {
                      const maxMag = data.shap_contributions[0]?.magnitude || 0.01;
                      return (
                        <div key={i} style={{ marginBottom: 6 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                            <span style={{ fontSize: 11, color: "rgba(255,255,255,0.7)" }}>{c.label}</span>
                            <span style={{ fontSize: 11, color: impactColor(c.impact), fontWeight: 600 }}>
                              {c.impact === "positive" ? "↑" : "↓"}
                            </span>
                          </div>
                          <div style={{ height: 4, background: "rgba(255,255,255,0.08)", borderRadius: 2, overflow: "hidden" }}>
                            <div style={{
                              height: "100%", borderRadius: 2,
                              width: `${(c.magnitude / maxMag) * 100}%`,
                              background: impactColor(c.impact),
                              transition: "width 0.6s ease",
                            }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
