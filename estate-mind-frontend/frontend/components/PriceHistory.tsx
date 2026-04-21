"use client";
/**
 * Estate Mind — PriceHistory + Prophet Forecast
 * Affiche l'historique des prix ET la prédiction Prophet à 3 mois.
 * Utilisé dans : app/portefeuille/page.tsx, app/territoire/page.tsx
 */
import { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceLine, Area, AreaChart, Legend
} from "recharts";
import { TrendingDown, TrendingUp, Minus, Sparkles } from "lucide-react";

interface PricePoint { date: string; price: number; }
interface ForecastPoint {
  date: string; yhat: number;
  yhat_lower: number; yhat_upper: number;
}

interface Props {
  listingUrl?:  string;
  savedPrice?:  number;
  currentPrice?:number;
  zone?:        string;     // si fourni, charge le forecast Prophet pour la zone
  title?:       string;
  compact?:     boolean;
}

// Génère historique démo
function genHistory(saved: number, current: number): PricePoint[] {
  const pts: PricePoint[] = [];
  const now = new Date();
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now); d.setDate(d.getDate() - i * 14);
    const prog = (6 - i) / 6;
    const base = saved + (current - saved) * prog;
    const noise = (Math.random() - .5) * saved * .02;
    pts.push({ date: d.toISOString().slice(0, 10), price: Math.round(i === 0 ? current : base + noise) });
  }
  return pts;
}

const TOOLTIP_STYLE = {
  background: "var(--el)", border: "1px solid var(--bor)",
  borderRadius: 8, fontSize: 11,
};

export function PriceHistory({ listingUrl, savedPrice = 0, currentPrice = 0, zone, title, compact = false }: Props) {
  const [history,   setHistory]   = useState<PricePoint[]>([]);
  const [forecast,  setForecast]  = useState<ForecastPoint[]>([]);
  const [fcInfo,    setFcInfo]    = useState<any>(null);
  const [loading,   setLoading]   = useState(true);
  const [showForecast, setShowForecast] = useState(false);

  useEffect(() => {
    // Historique
    if (savedPrice > 0 && currentPrice > 0) {
      setHistory(genHistory(savedPrice, currentPrice));
    }

    // Forecast Prophet si zone fournie
    if (zone) {
      fetch(`/api/forecast/${encodeURIComponent(zone)}?periods=90&freq=W`)
        .then(r => r.ok ? r.json() : null)
        .then(d => {
          if (d && !d.error) {
            setForecast(d.forecast || []);
            setFcInfo(d);
          }
        })
        .catch(() => {});
    }
    setLoading(false);
  }, [savedPrice, currentPrice, zone]);

  if (loading) return <div style={{ fontSize: 11, color: "var(--mut)" }}>Chargement...</div>;

  const delta  = currentPrice - savedPrice;
  const deltaP = savedPrice > 0 ? delta / savedPrice * 100 : 0;
  const hasDrop= delta < 0;
  const chartC = hasDrop ? "#52C896" : delta > 0 ? "#E05C5C" : "var(--gold)";

  // Mode compact : sparkline seul
  if (compact && history.length > 0) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ width: 72, height: 28 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={history}>
              <Line type="monotone" dataKey="price" stroke={chartC} strokeWidth={1.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <span style={{ fontSize: 11, fontWeight: 600, color: chartC }}>
          {delta > 0 ? "+" : ""}{deltaP.toFixed(1)}%
        </span>
      </div>
    );
  }

  // ── Mode complet ──────────────────────────────────────────────────────────
  // Prépare les données pour le graphique combiné (historique + forecast)
  const chartData = [
    ...history.map(h => ({ date: h.date, historical: h.price })),
    ...(showForecast ? forecast.map(f => ({
      date:     f.date,
      forecast: f.yhat,
      lower:    f.yhat_lower,
      upper:    f.yhat_upper,
    })) : []),
  ];

  const trendColor = fcInfo?.trend === "hausse" ? "#52C896"
                   : fcInfo?.trend === "baisse" ? "#E05C5C"
                   : "var(--mut)";

  return (
    <div style={{ background: "var(--el)", borderRadius: 10, padding: "14px 16px", marginTop: 12 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 11, fontWeight: 500 }}>Historique des prix</span>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {/* Delta historique */}
          {savedPrice > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              {hasDrop ? <TrendingDown size={12} color={chartC}/> : <TrendingUp size={12} color={chartC}/>}
              <span style={{ fontSize: 12, fontWeight: 600, color: chartC }}>
                {delta > 0 ? "+" : ""}{deltaP.toFixed(1)}%
              </span>
            </div>
          )}
          {/* Bouton Prophet */}
          {forecast.length > 0 && (
            <button onClick={() => setShowForecast(s => !s)} style={{
              display: "flex", alignItems: "center", gap: 4,
              padding: "3px 8px", borderRadius: 6,
              border: `1px solid ${showForecast ? "rgba(200,169,110,.4)" : "var(--bor)"}`,
              background: showForecast ? "rgba(200,169,110,.1)" : "transparent",
              color: showForecast ? "var(--gold)" : "var(--mut)",
              cursor: "pointer", fontSize: 10, fontFamily: "var(--font-body)",
            }}>
              <Sparkles size={9} />
              Prophet {showForecast ? "actif" : "→"}
            </button>
          )}
        </div>
      </div>

      {/* Graphique */}
      <ResponsiveContainer width="100%" height={120}>
        <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="fcGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="var(--gold)" stopOpacity={0.15}/>
              <stop offset="95%" stopColor="var(--gold)" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <XAxis dataKey="date" tick={{ fontSize: 9, fill: "var(--mut)" }} axisLine={false} tickLine={false}
            tickFormatter={d => new Date(d).toLocaleDateString("fr-FR", { day:"2-digit", month:"short" })}
            interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 9, fill: "var(--mut)" }} axisLine={false} tickLine={false}
            tickFormatter={v => `${(v/1000).toFixed(0)}K`} width={30} />
          <Tooltip contentStyle={TOOLTIP_STYLE}
            formatter={(v: number, n: string) => [
              `${v?.toLocaleString("fr-TN")} TND`,
              n === "historical" ? "Historique" : n === "forecast" ? "Prédiction" : n
            ]} />
          {/* Ligne de référence prix sauvegardé */}
          {savedPrice > 0 && (
            <ReferenceLine y={savedPrice} stroke="var(--mut)"
              strokeDasharray="4 3" strokeWidth={1}/>
          )}
          {/* Historique */}
          <Line type="monotone" dataKey="historical" stroke={chartC}
            strokeWidth={2} dot={false} connectNulls />
          {/* Forecast Prophet */}
          {showForecast && (
            <>
              <Area type="monotone" dataKey="upper" stroke="none"
                fill="url(#fcGrad)" fillOpacity={1} />
              <Area type="monotone" dataKey="lower" stroke="none"
                fill="white" fillOpacity={0.8} />
              <Line type="monotone" dataKey="forecast" stroke="var(--gold)"
                strokeWidth={2} strokeDasharray="6 3" dot={false} connectNulls />
            </>
          )}
        </AreaChart>
      </ResponsiveContainer>

      {/* Légende */}
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 10, color: "var(--mut)", flexWrap: "wrap", gap: 6 }}>
        {savedPrice > 0 && (
          <>
            <span>Sauvegardé : <b style={{ color: "var(--txt)" }}>{savedPrice.toLocaleString("fr-TN")} TND</b></span>
            <span>Actuel : <b style={{ color: chartC }}>{currentPrice.toLocaleString("fr-TN")} TND</b></span>
          </>
        )}
        {/* Résumé Prophet */}
        {showForecast && fcInfo && (
          <div style={{ width: "100%", display: "flex", gap: 12, alignItems: "center",
            padding: "8px 10px", borderRadius: 7, background: "rgba(200,169,110,.06)",
            border: "1px solid rgba(200,169,110,.2)", marginTop: 6 }}>
            <Sparkles size={11} color="var(--gold)" />
            <span style={{ color: "var(--gold)", fontWeight: 500, fontSize: 11 }}>Prophet</span>
            <span style={{ fontSize: 10 }}>
              Tendance <b style={{ color: trendColor }}>{fcInfo.trend}</b>
              {fcInfo.trend_pct !== undefined && (
                <span> ({fcInfo.trend_pct > 0 ? "+" : ""}{fcInfo.trend_pct?.toFixed(1)}% sur 90j)</span>
              )}
            </span>
            <span style={{ fontSize: 10 }}>
              Prix prédit fin : <b style={{ color: "var(--gold)" }}>
                {fcInfo.predicted_price_end?.toLocaleString("fr-TN")} TND
              </b>
            </span>
            <span style={{ fontSize: 9, marginLeft: "auto" }}>
              {fcInfo.method === "prophet" ? "🔮 Facebook Prophet" : "📈 Régression (fallback)"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
