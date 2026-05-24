"use client";

import { useState } from "react";
import {
  RadarChart, PolarGrid, PolarAngleAxis,
  Radar, ResponsiveContainer, Tooltip, Legend,
} from "recharts";

// ── Données d'attractivité (5 axes) ──────────────────────────────────────────
// Score [0-100] sur 5 dimensions pour chaque gouvernorat

const ATTRACTIVENESS_DATA: Record<string, {
  prix: number;       // 100 = très abordable, 0 = très cher
  croissance: number; // 100 = forte hausse, 0 = déclin
  volume: number;     // 100 = très actif, 0 = inactif
  infrastructure: number; // 100 = très bien équipé
  potentiel: number;  // 100 = fort potentiel de valorisation
  label_prix: string;
  label_tendance: string;
}> = {
  "Tunis":    { prix:40,  croissance:65, volume:95,  infrastructure:95,  potentiel:70, label_prix:"3 200 TND/m²", label_tendance:"↑ +8.6%" },
  "Hammamet": { prix:30,  croissance:85, volume:72,  infrastructure:78,  potentiel:90, label_prix:"3 800 TND/m²", label_tendance:"↑ +15.2%"},
  "Nabeul":   { prix:55,  croissance:75, volume:80,  infrastructure:72,  potentiel:85, label_prix:"2 600 TND/m²", label_tendance:"↑ +12.2%"},
  "Sousse":   { prix:45,  croissance:70, volume:85,  infrastructure:82,  potentiel:80, label_prix:"2 800 TND/m²", label_tendance:"↑ +10.2%"},
  "Monastir": { prix:48,  croissance:62, volume:74,  infrastructure:80,  potentiel:75, label_prix:"2 600 TND/m²", label_tendance:"↑ +8.1%" },
  "Sfax":     { prix:62,  croissance:40, volume:78,  infrastructure:80,  potentiel:60, label_prix:"2 100 TND/m²", label_tendance:"→ +4.1%" },
  "Mahdia":   { prix:72,  croissance:68, volume:52,  infrastructure:58,  potentiel:82, label_prix:"1 800 TND/m²", label_tendance:"↑ +8.4%" },
  "Bizerte":  { prix:68,  croissance:45, volume:58,  infrastructure:68,  potentiel:65, label_prix:"1 800 TND/m²", label_tendance:"↑ +5.5%" },
  "Tozeur":   { prix:76,  croissance:58, volume:35,  infrastructure:52,  potentiel:78, label_prix:"1 200 TND/m²", label_tendance:"↑ +7.2%" },
  "Médenine": { prix:78,  croissance:62, volume:48,  infrastructure:55,  potentiel:72, label_prix:"1 500 TND/m²", label_tendance:"↑ +8.1%" },
  "Kasserine":{ prix:90,  croissance:20, volume:25,  infrastructure:35,  potentiel:30, label_prix:"700 TND/m²",  label_tendance:"↓ -9.3%" },
  "Gafsa":    { prix:88,  croissance:28, volume:30,  infrastructure:42,  potentiel:38, label_prix:"800 TND/m²",  label_tendance:"↓ -3.2%" },
};

const ZONE_LIST = Object.keys(ATTRACTIVENESS_DATA);

const COLORS = {
  primary:   "#C8A96E",
  secondary: "#52C896",
  grid:      "rgba(255,255,255,0.08)",
  text:      "rgba(242,240,236,0.6)",
};

const AXES = [
  { key: "prix",          label: "Prix\nabordable" },
  { key: "croissance",    label: "Croissance" },
  { key: "volume",        label: "Activité" },
  { key: "infrastructure",label: "Infrastructure" },
  { key: "potentiel",     label: "Potentiel" },
];

function buildRadarData(zones: string[]) {
  return AXES.map(axis => {
    const row: Record<string, any> = { axis: axis.label };
    zones.forEach(z => {
      row[z] = ATTRACTIVENESS_DATA[z]?.[axis.key as keyof typeof ATTRACTIVENESS_DATA[string]] ?? 0;
    });
    return row;
  });
}

function ScoreGauge({ score, label, color }: { score: number; label: string; color: string }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{
        fontFamily: "var(--font-display)", fontSize: 22,
        fontWeight: 700, color,
      }}>{score}</div>
      <div style={{
        height: 3, background: "var(--el)", borderRadius: 2,
        margin: "4px 0", overflow: "hidden",
      }}>
        <div style={{
          height: "100%", width: `${score}%`,
          background: color, borderRadius: 2,
          transition: "width .6s ease",
        }} />
      </div>
      <div style={{ fontSize: 9, color: "var(--mut)", textTransform: "uppercase", letterSpacing: ".05em" }}>
        {label}
      </div>
    </div>
  );
}

export function AttractivenessRadar() {
  const [zone1, setZone1] = useState("Hammamet");
  const [zone2, setZone2] = useState("Mahdia");
  const [compare, setCompare] = useState(true);

  const zones     = compare ? [zone1, zone2] : [zone1];
  const radarData = buildRadarData(zones);
  const d1        = ATTRACTIVENESS_DATA[zone1];
  const d2        = ATTRACTIVENESS_DATA[zone2];

  const score1 = Math.round((d1.prix + d1.croissance + d1.volume + d1.infrastructure + d1.potentiel) / 5);
  const score2 = Math.round((d2.prix + d2.croissance + d2.volume + d2.infrastructure + d2.potentiel) / 5);

  return (
    <div className="card" style={{ padding: 22 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--info)" }} />
          <span style={{ fontFamily: "var(--font-display)", fontSize: 15, fontWeight: 600 }}>
            Score d'attractivité
          </span>
        </div>
        <button
          onClick={() => setCompare(c => !c)}
          style={{
            padding: "4px 10px", borderRadius: 6, fontSize: 11,
            border: "1px solid var(--bor)", background: compare ? "var(--gdim)" : "transparent",
            color: compare ? "var(--gold)" : "var(--mut)",
            cursor: "pointer", fontFamily: "var(--font-body)",
          }}
        >
          {compare ? "Mode comparaison" : "Zone unique"}
        </button>
      </div>

      {/* Sélecteurs */}
      <div style={{ display: "flex", gap: 10, marginBottom: 16, alignItems: "center" }}>
        <select value={zone1} onChange={e => setZone1(e.target.value)} style={{
          flex: 1, padding: "6px 10px", borderRadius: 7, fontSize: 12,
          border: "1px solid #C8A96E44", background: "#C8A96E0A", color: "#C8A96E",
        }}>
          {ZONE_LIST.map(z => <option key={z} value={z}>{z}</option>)}
        </select>

        {compare && (
          <>
            <span style={{ color: "var(--mut)", fontSize: 11 }}>vs</span>
            <select value={zone2} onChange={e => setZone2(e.target.value)} style={{
              flex: 1, padding: "6px 10px", borderRadius: 7, fontSize: 12,
              border: "1px solid #52C89644", background: "#52C8960A", color: "#52C896",
            }}>
              {ZONE_LIST.filter(z => z !== zone1).map(z => <option key={z} value={z}>{z}</option>)}
            </select>
          </>
        )}
      </div>

      {/* Radar chart */}
      <ResponsiveContainer width="100%" height={240}>
        <RadarChart data={radarData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
          <PolarGrid stroke={COLORS.grid} />
          <PolarAngleAxis
            dataKey="axis"
            tick={{ fill: COLORS.text, fontSize: 10 }}
          />
          <Radar
            name={zone1}
            dataKey={zone1}
            stroke={COLORS.primary}
            fill={COLORS.primary}
            fillOpacity={0.25}
            strokeWidth={2}
          />
          {compare && (
            <Radar
              name={zone2}
              dataKey={zone2}
              stroke={COLORS.secondary}
              fill={COLORS.secondary}
              fillOpacity={0.18}
              strokeWidth={2}
              strokeDasharray="5 3"
            />
          )}
          <Tooltip
            contentStyle={{
              background: "var(--card)", border: "1px solid var(--bor)",
              borderRadius: 8, fontSize: 11,
            }}
            formatter={(v: number, name: string) => [`${v}/100`, name]}
          />
          <Legend wrapperStyle={{ fontSize: 11, color: "var(--mut)" }} />
        </RadarChart>
      </ResponsiveContainer>

      {/* Scores détaillés */}
      <div style={{
        display: "grid",
        gridTemplateColumns: compare ? "1fr auto 1fr" : "1fr",
        gap: 12, marginTop: 12,
        borderTop: "1px solid var(--bor)", paddingTop: 14,
      }}>
        {/* Zone 1 */}
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#C8A96E", marginBottom: 10, textAlign: "center" }}>
            {zone1}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {AXES.slice(0, 4).map(a => (
              <ScoreGauge
                key={a.key}
                score={d1[a.key as keyof typeof d1] as number}
                label={a.key}
                color="#C8A96E"
              />
            ))}
          </div>
          <div style={{ marginTop: 8, textAlign: "center" }}>
            <span style={{
              fontSize: 9, padding: "2px 8px", borderRadius: 999,
              background: "#C8A96E14", color: "#C8A96E",
              border: "1px solid #C8A96E28",
            }}>
              {d1.label_tendance}
            </span>
          </div>
          <div style={{ marginTop: 10, textAlign: "center" }}>
            <div style={{ fontFamily: "var(--font-display)", fontSize: 28, fontWeight: 700, color: "#C8A96E" }}>
              {score1}
            </div>
            <div style={{ fontSize: 10, color: "var(--mut)" }}>score global / 100</div>
          </div>
        </div>

        {/* Séparateur */}
        {compare && (
          <div style={{ width: 1, background: "var(--bor)", margin: "0 8px" }} />
        )}

        {/* Zone 2 */}
        {compare && (
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#52C896", marginBottom: 10, textAlign: "center" }}>
              {zone2}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {AXES.slice(0, 4).map(a => (
                <ScoreGauge
                  key={a.key}
                  score={d2[a.key as keyof typeof d2] as number}
                  label={a.key}
                  color="#52C896"
                />
              ))}
            </div>
            <div style={{ marginTop: 8, textAlign: "center" }}>
              <span style={{
                fontSize: 9, padding: "2px 8px", borderRadius: 999,
                background: "#52C89614", color: "#52C896",
                border: "1px solid #52C89628",
              }}>
                {d2.label_tendance}
              </span>
            </div>
            <div style={{ marginTop: 10, textAlign: "center" }}>
              <div style={{ fontFamily: "var(--font-display)", fontSize: 28, fontWeight: 700, color: "#52C896" }}>
                {score2}
              </div>
              <div style={{ fontSize: 10, color: "var(--mut)" }}>score global / 100</div>
            </div>
          </div>
        )}
      </div>

      {/* Verdict comparaison */}
      {compare && score1 !== score2 && (
        <div style={{
          marginTop: 14, padding: "10px 14px", borderRadius: 8,
          background: score1 > score2 ? "#C8A96E0A" : "#52C8960A",
          border: `1px solid ${score1 > score2 ? "#C8A96E28" : "#52C89628"}`,
          fontSize: 12, textAlign: "center",
          color: score1 > score2 ? "#C8A96E" : "#52C896",
        }}>
          {score1 > score2
            ? `${zone1} est plus attractif (+${score1 - score2} pts) — meilleur rapport croissance/infrastructure`
            : `${zone2} est plus attractif (+${score2 - score1} pts) — meilleur potentiel de valorisation`
          }
        </div>
      )}
    </div>
  );
}
