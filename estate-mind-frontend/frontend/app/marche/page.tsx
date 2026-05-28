"use client";
import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { TrendingUp, MapPin, Building2 } from "lucide-react";
import { KpiCard } from "@/components/KpiCard";
import { XAIMarketPanel } from "@/components/XAIMarketPanel";
import { getMarket } from "@/lib/api";
import type { MarketOverview } from "@/types";

const FALLBACK: MarketOverview = {
  total: 6877, median_ppm2: 2500, mean_ppm2: 2750, top_city: "Tunis",
  cities: [
    { city:"Tunis",     ppm2:3200, n:2341, median:3200, mean:3400 },
    { city:"La Marsa",  ppm2:4800, n:892,  median:4800, mean:5100 },
    { city:"Ariana",    ppm2:2665, n:734,  median:2665, mean:2800 },
    { city:"Hammamet",  ppm2:3900, n:1203, median:3900, mean:4100 },
    { city:"Nabeul",    ppm2:2251, n:654,  median:2251, mean:2400 },
    { city:"Sousse",    ppm2:2800, n:1098, median:2800, mean:2950 },
    { city:"Sfax",      ppm2:1857, n:876,  median:1857, mean:2000 },
    { city:"Bizerte",   ppm2:2505, n:432,  median:2505, mean:2600 },
  ],
  property_types: { appartement:56, villa:16, bureau_local:12, terrain:11, maison:4, studio:1 },
};

// Villes pour lesquelles Prophet a un forecast
const FORECAST_CITIES = ["Tunis","Ariana","Nabeul","Sousse","Ben Arous","Bizerte","Mahdia","Sfax","La Manouba"];

export default function MarchePage() {
  const [data,     setData]     = useState<MarketOverview>(FALLBACK);
  const [city,     setCity]     = useState("");
  const [propType, setPropType] = useState("");
  const [xaiCity,  setXaiCity]  = useState<string | null>(null);

  const load = () =>
    getMarket(city || undefined, propType || undefined)
      .then(setData)
      .catch(() => setData(FALLBACK));

  useEffect(() => { load(); }, []);

  const sorted = [...data.cities].sort((a, b) => b.ppm2 - a.ppm2);
  const max    = sorted[0]?.ppm2 ?? 1;

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:20 }}>
      <div style={{ marginBottom:8 }}>
        <h1 style={{ fontFamily:"var(--font-display)", fontSize:24, fontWeight:600, marginBottom:4 }}>
          Vue du marché
        </h1>
        <p style={{ fontSize:13, color:"var(--mut)" }}>
          Prix au m² et statistiques par ville et type de bien
        </p>
      </div>

      {/* Filtres */}
      <div style={{ display:"flex", gap:12, alignItems:"flex-end" }}>
        <div style={{ flex:1 }}>
          <label style={{ fontSize:11, color:"var(--mut)", textTransform:"uppercase",
            letterSpacing:".06em", display:"block", marginBottom:6 }}>Ville</label>
          <input value={city} onChange={e => setCity(e.target.value)}
            placeholder="Toutes les villes" />
        </div>
        <div style={{ flex:1 }}>
          <label style={{ fontSize:11, color:"var(--mut)", textTransform:"uppercase",
            letterSpacing:".06em", display:"block", marginBottom:6 }}>Type de bien</label>
          <select value={propType} onChange={e => setPropType(e.target.value)}>
            <option value="">Tous les types</option>
            {["appartement","villa","terrain","maison","studio","bureau_local"].map(t => (
              <option key={t} value={t}>{t.replace("_"," ")}</option>
            ))}
          </select>
        </div>
        <button className="btn-secondary" onClick={load}>Filtrer</button>
      </div>

      {/* KPIs */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:14 }}>
        <KpiCard
          label="Prix médian national"
          value={`${data.median_ppm2.toLocaleString("fr-FR")} TND/m²`}
          sub={`${data.total.toLocaleString("fr-FR")} annonces`}
          Icon={TrendingUp} accent="var(--info)"
        />
        <KpiCard
          label="Ville la plus chère"
          value={data.top_city}
          sub={`${(sorted[0]?.ppm2 ?? 0).toLocaleString("fr-FR")} TND/m² médiane`}
          Icon={MapPin}
        />
        <KpiCard
          label="Villes couvertes"
          value={data.cities.length}
          sub="marchés analysés"
          Icon={Building2} accent="var(--ok)"
        />
      </div>

      {/* Bar chart */}
      <div className="card" style={{ padding:24 }}>
        <div className="section-title" style={{ marginBottom:22 }}>
          Prix médian au m² par ville (TND)
        </div>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={sorted} barSize={34}>
            <XAxis dataKey="city" tick={{ fill:"var(--mut)", fontSize:11 }}
              axisLine={false} tickLine={false} />
            <YAxis tick={{ fill:"var(--mut)", fontSize:10 }}
              axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ background:"var(--el)", border:"1px solid var(--bor)",
                borderRadius:8, color:"var(--txt)" }}
              formatter={(v: number) => [`${v.toLocaleString("fr-FR")} TND/m²`, "Prix médian"]}
            />
            <Bar dataKey="ppm2" fill="var(--gold)" fillOpacity={0.82} radius={[4,4,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Table avec XAI intégré */}
      <div className="card" style={{ overflow:"hidden" }}>
        <div style={{ padding:"18px 22px", borderBottom:"1px solid var(--bor)" }}>
          <div className="section-title">Détail par ville</div>
          <div style={{ fontSize:11, color:"var(--mut)", marginTop:4 }}>
            Cliquez sur 🔍 pour obtenir l'explication IA de la prévision de prix
          </div>
        </div>

        <table className="data-table" style={{ padding:0 }}>
          <thead>
            <tr style={{ background:"var(--el)" }}>
              {["Ville","Annonces","Prix/m² médian","Rang","XAI Prévision"].map(h => (
                <th key={h} style={{ padding:"11px 22px" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((d, i) => (
              <>
                <tr key={d.city} style={{ borderTop:"1px solid var(--bor)" }}>
                  {/* Ville */}
                  <td style={{ padding:"13px 22px" }}>{d.city}</td>

                  {/* Annonces */}
                  <td style={{ padding:"13px 22px", color:"var(--mut)", fontSize:12 }}>
                    {d.n.toLocaleString("fr-FR")} ann.
                  </td>

                  {/* Prix/m² */}
                  <td style={{ padding:"13px 22px" }}>
                    <div style={{ display:"flex", alignItems:"center", gap:12 }}>
                      <div className="bar-bg" style={{ width:100 }}>
                        <div className="bar-fill"
                          style={{ width:`${d.ppm2/max*100}%`, background:"var(--gold)" }} />
                      </div>
                      <span style={{ fontFamily:"var(--font-display)", fontWeight:600, fontSize:13 }}>
                        {d.ppm2.toLocaleString("fr-FR")} TND
                      </span>
                    </div>
                  </td>

                  {/* Rang */}
                  <td style={{ padding:"13px 22px", fontSize:11,
                    color: i===0 ? "var(--gold)" : "var(--mut)" }}>
                    {i===0 ? "▲ plus cher" : `#${i+1}`}
                  </td>

                  {/* Bouton XAI */}
                  <td style={{ padding:"8px 22px" }}>
                    {FORECAST_CITIES.includes(d.city) ? (
                      <button
                        onClick={() => setXaiCity(xaiCity === d.city ? null : d.city)}
                        style={{
                          padding:"5px 10px", borderRadius:6, cursor:"pointer",
                          background: xaiCity === d.city
                            ? "rgba(200,169,110,0.15)" : "rgba(200,169,110,0.06)",
                          border:"1px solid rgba(200,169,110,0.3)",
                          color:"var(--gold)", fontSize:11, fontWeight:500,
                          fontFamily:"inherit",
                        }}
                      >
                        {xaiCity === d.city ? "▲ Fermer" : "🔍 Expliquer"}
                      </button>
                    ) : (
                      <span style={{ fontSize:11, color:"var(--mut)" }}>—</span>
                    )}
                  </td>
                </tr>

                {/* Panneau XAI dépliable sous la ligne */}
                {xaiCity === d.city && (
                  <tr key={`${d.city}-xai`}
                    style={{ borderTop:"none", background:"rgba(200,169,110,0.02)" }}>
                    <td colSpan={5} style={{ padding:"0 22px 16px" }}>
                      <XAIMarketPanel city={d.city} />
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
