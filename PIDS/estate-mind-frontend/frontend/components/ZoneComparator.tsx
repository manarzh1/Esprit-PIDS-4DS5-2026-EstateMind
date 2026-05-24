"use client";

import { useState, useCallback } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine,
} from "recharts";
import { Plus, X, TrendingUp, TrendingDown, Minus } from "lucide-react";

// ── Couleurs des zones comparées ──────────────────────────────────────────────
const ZONE_COLORS = ["#C8A96E", "#52C896", "#7F77DD", "#E05C5C", "#52C8C8"];

// ── Données démo ──────────────────────────────────────────────────────────────
const DEMO_SERIES: Record<string, { period: string; median_price: number; volume: number }[]> = {
  "Tunis":    [
    {period:"2025-09",median_price:290000,volume:312},{period:"2025-10",median_price:295000,volume:334},
    {period:"2025-11",median_price:298000,volume:298},{period:"2025-12",median_price:302000,volume:276},
    {period:"2026-01",median_price:308000,volume:388},{period:"2026-02",median_price:315000,volume:412},
  ],
  "Sousse":   [
    {period:"2025-09",median_price:225000,volume:198},{period:"2025-10",median_price:230000,volume:210},
    {period:"2025-11",median_price:228000,volume:187},{period:"2025-12",median_price:235000,volume:205},
    {period:"2026-01",median_price:242000,volume:231},{period:"2026-02",median_price:248000,volume:254},
  ],
  "Hammamet": [
    {period:"2025-09",median_price:330000,volume:88}, {period:"2025-10",median_price:340000,volume:95},
    {period:"2025-11",median_price:348000,volume:102},{period:"2025-12",median_price:355000,volume:118},
    {period:"2026-01",median_price:368000,volume:134},{period:"2026-02",median_price:380000,volume:142},
  ],
  "Nabeul":   [
    {period:"2025-09",median_price:196000,volume:112},{period:"2025-10",median_price:200000,volume:128},
    {period:"2025-11",median_price:205000,volume:119},{period:"2025-12",median_price:208000,volume:134},
    {period:"2026-01",median_price:215000,volume:156},{period:"2026-02",median_price:220000,volume:163},
  ],
  "Mahdia":   [
    {period:"2025-09",median_price:155000,volume:54}, {period:"2025-10",median_price:157000,volume:58},
    {period:"2025-11",median_price:160000,volume:62}, {period:"2025-12",median_price:162000,volume:71},
    {period:"2026-01",median_price:165000,volume:78}, {period:"2026-02",median_price:168000,volume:87},
  ],
  "Sfax":     [
    {period:"2025-09",median_price:170000,volume:134},{period:"2025-10",median_price:172000,volume:142},
    {period:"2025-11",median_price:174000,volume:138},{period:"2025-12",median_price:175000,volume:129},
    {period:"2026-01",median_price:176000,volume:148},{period:"2026-02",median_price:177000,volume:152},
  ],
};

const AVAILABLE_ZONES = Object.keys(DEMO_SERIES);

// ── Calcul de tendance ────────────────────────────────────────────────────────
function calcTrend(pts: { median_price: number }[]) {
  if (pts.length < 2) return 0;
  const first = pts[0].median_price;
  const last  = pts[pts.length - 1].median_price;
  return (last - first) / first * 100;
}

// ── Fusion des séries pour Recharts ──────────────────────────────────────────
function mergeSeries(zones: string[], data: Record<string, typeof DEMO_SERIES[string]>) {
  const periods = new Set<string>();
  zones.forEach(z => (data[z] || []).forEach(p => periods.add(p.period)));
  const sorted = [...periods].sort();

  return sorted.map(period => {
    const row: Record<string, any> = { period };
    zones.forEach(z => {
      const pt = (data[z] || []).find(p => p.period === period);
      if (pt) row[z] = pt.median_price;
    });
    return row;
  });
}

// ── Tooltip custom ────────────────────────────────────────────────────────────
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "var(--card)", border: "1px solid var(--bor)",
      borderRadius: 8, padding: "10px 14px", fontSize: 12,
    }}>
      <div style={{ color: "var(--mut)", fontSize: 10, marginBottom: 6 }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: p.color }} />
          <span style={{ color: "var(--mut)" }}>{p.dataKey} :</span>
          <span style={{ color: p.color, fontWeight: 600 }}>
            {p.value?.toLocaleString("fr-TN")} TND
          </span>
        </div>
      ))}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// COMPOSANT PRINCIPAL
// ══════════════════════════════════════════════════════════════════════════════

export function ZoneComparator() {
  const [selectedZones, setSelectedZones] = useState<string[]>(["Tunis", "Sousse", "Hammamet"]);
  const [metric,  setMetric]  = useState<"price"|"volume">("price");
  const [loading, setLoading] = useState(false);
  const [seriesData, setSeriesData] = useState<typeof DEMO_SERIES>(DEMO_SERIES);

  const addZone = (zone: string) => {
    if (selectedZones.includes(zone) || selectedZones.length >= 5) return;
    setSelectedZones(prev => [...prev, zone]);
  };

  const removeZone = (zone: string) => {
    if (selectedZones.length <= 1) return;
    setSelectedZones(prev => prev.filter(z => z !== zone));
  };

  const loadRealData = useCallback(async () => {
    setLoading(true);
    try {
      const fetches = selectedZones.map(zone =>
        fetch(`/api/territorial/time-series?group_by=city&freq=M&zone=${encodeURIComponent(zone)}`)
          .then(r => r.ok ? r.json() : null)
      );
      const results = await Promise.all(fetches);
      const newData: typeof DEMO_SERIES = { ...DEMO_SERIES };
      results.forEach((res, i) => {
        const zone   = selectedZones[i];
        const series = res?.series?.[zone];
        if (series?.length) newData[zone] = series;
      });
      setSeriesData(newData);
    } catch { /* garde les données démo */ }
    setLoading(false);
  }, [selectedZones]);

  const chartData = mergeSeries(selectedZones, seriesData);
  const dataKey   = metric === "price" ? (z: string) => z : (z: string) => `${z}_vol`;

  return (
    <div className="card" style={{ padding: 22 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--gold)" }} />
          <span style={{ fontFamily: "var(--font-display)", fontSize: 15, fontWeight: 600 }}>
            Comparateur de zones
          </span>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {/* Toggle métrique */}
          <div style={{
            display: "flex", gap: 3, background: "var(--el)",
            padding: 3, borderRadius: 7, border: "1px solid var(--bor)",
          }}>
            {[{ id: "price", label: "Prix" }, { id: "volume", label: "Volume" }].map(m => (
              <button key={m.id} onClick={() => setMetric(m.id as any)} style={{
                padding: "4px 10px", borderRadius: 5, border: "none",
                background: metric === m.id ? "var(--card)" : "transparent",
                color: metric === m.id ? "var(--gold)" : "var(--mut)",
                fontSize: 11, fontFamily: "var(--font-body)", cursor: "pointer",
              }}>{m.label}</button>
            ))}
          </div>
        </div>
      </div>

      {/* Sélecteur de zones */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 14 }}>
        {selectedZones.map((zone, i) => (
          <div key={zone} style={{
            display: "flex", alignItems: "center", gap: 5,
            padding: "4px 10px", borderRadius: 999,
            background: `${ZONE_COLORS[i]}18`,
            border: `1px solid ${ZONE_COLORS[i]}40`,
          }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: ZONE_COLORS[i] }} />
            <span style={{ fontSize: 11, color: ZONE_COLORS[i], fontWeight: 500 }}>{zone}</span>
            <button onClick={() => removeZone(zone)} style={{
              background: "none", border: "none", cursor: "pointer",
              color: ZONE_COLORS[i], padding: 0, lineHeight: 1,
            }}>
              <X size={10} />
            </button>
          </div>
        ))}

        {selectedZones.length < 5 && (
          <select
            value=""
            onChange={e => { if (e.target.value) addZone(e.target.value); }}
            style={{
              padding: "4px 10px", borderRadius: 999, fontSize: 11,
              border: "1px dashed var(--bor)", background: "var(--el)",
              color: "var(--mut)", cursor: "pointer",
            }}
          >
            <option value="">+ Ajouter une zone</option>
            {AVAILABLE_ZONES.filter(z => !selectedZones.includes(z)).map(z => (
              <option key={z} value={z}>{z}</option>
            ))}
          </select>
        )}
      </div>

      {/* Graphique principal */}
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData}>
          <XAxis dataKey="period"
            tick={{ fontSize: 10, fill: "var(--mut)" }}
            axisLine={false} tickLine={false} />
          <YAxis
            tick={{ fontSize: 10, fill: "var(--mut)" }}
            axisLine={false} tickLine={false}
            tickFormatter={v => metric === "price" ? `${(v/1000).toFixed(0)}K` : `${v}`} />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ fontSize: 11, color: "var(--mut)" }} />
          {selectedZones.map((zone, i) => (
            <Line
              key={zone}
              type="monotone"
              dataKey={zone}
              name={zone}
              stroke={ZONE_COLORS[i]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: ZONE_COLORS[i] }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>

      {/* Scorecard des tendances */}
      <div style={{
        display: "grid",
        gridTemplateColumns: `repeat(${Math.min(selectedZones.length, 5)}, 1fr)`,
        gap: 8, marginTop: 14,
      }}>
        {selectedZones.map((zone, i) => {
          const pts   = seriesData[zone] || [];
          const trend = calcTrend(pts);
          const color = ZONE_COLORS[i];
          const lastPrice = pts[pts.length - 1]?.median_price;

          return (
            <div key={zone} style={{
              background: `${color}08`, border: `1px solid ${color}22`,
              borderRadius: 8, padding: "10px 12px", textAlign: "center",
            }}>
              <div style={{ fontSize: 10, color: "var(--mut)", marginBottom: 4 }}>{zone}</div>
              {lastPrice && (
                <div style={{ fontFamily: "var(--font-display)", fontSize: 14, fontWeight: 600, color, marginBottom: 3 }}>
                  {(lastPrice / 1000).toFixed(0)}K TND
                </div>
              )}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 3 }}>
                {trend > 0
                  ? <TrendingUp  size={10} color="#52C896" />
                  : trend < 0
                    ? <TrendingDown size={10} color="#E05C5C" />
                    : <Minus size={10} color="var(--mut)" />
                }
                <span style={{
                  fontSize: 11, fontWeight: 600,
                  color: trend > 0 ? "#52C896" : trend < 0 ? "#E05C5C" : "var(--mut)",
                }}>
                  {trend > 0 ? "+" : ""}{trend.toFixed(1)}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
