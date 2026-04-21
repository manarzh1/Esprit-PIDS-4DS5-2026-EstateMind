"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Target, Sparkles, TrendingUp,
  ChevronRight, MapPin, Home,
  RefreshCw, SlidersHorizontal, X,
} from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────
interface MatchedListing {
  title: string; city: string; property_type: string;
  price: number; surface: number; price_per_m2: number | null;
  trust_score: number; legal_risk_score: number;
  match_score: number; match_reasons: string[];
}
interface SimilarListing {
  title: string; city: string; property_type: string;
  price: number; surface: number; price_per_m2: number;
  trust_score: number; similarity_score: number; price_diff_pct: number;
}
interface InvestZone {
  city: string; investment_score: number; level: string;
  growth_rate_pct: number; demand_pressure: number;
  risk_score: number; avg_ppm2: number | null;
  n_listings: number; rationale: string;
  recommended_type: string; horizon_years: string;
}
interface RecoData {
  matching:      MatchedListing[];
  similaires:    SimilarListing[];
  investissement: InvestZone[];
  params:        { budget: number; surface_min: number; city: string; property_type: string; risk_tolerance: string };
}

// ── Helpers couleur ───────────────────────────────────────────────────────────
const TC = (s: number) => s >= .75 ? "var(--ok)" : s >= .5 ? "var(--warn)" : "var(--bad)";
const IC = (level: string) =>
  level === "Excellent" ? "var(--ok)"  :
  level === "Bon"       ? "#52C8C8"    :
  level === "Moyen"     ? "var(--warn)": "var(--mut)";

// ── Sous-composants ──────────────────────────────────────────────────────────

function ScoreBadge({ score, color }: { score: number; color: string }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 6, flexShrink: 0,
    }}>
      <div style={{ width: 36, height: 3, background: "rgba(255,255,255,.08)", borderRadius: 2, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${score * 100}%`, background: color, borderRadius: 2, transition: "width .5s ease" }} />
      </div>
      <span style={{ fontSize: 11, fontFamily: "var(--font-display)", fontWeight: 600, color, minWidth: 28 }}>
        {(score * 100).toFixed(0)}
      </span>
    </div>
  );
}

function ListingCard({ listing, rank, scoreKey, scoreLabel, scoreColor }:
  { listing: any; rank: number; scoreKey: string; scoreLabel: string; scoreColor: string }) {
  return (
    <div style={{
      display: "flex", gap: 12, padding: "12px 0",
      borderBottom: "1px solid var(--bor)",
      alignItems: "flex-start",
    }}>
      {/* Rang */}
      <div style={{
        width: 22, height: 22, borderRadius: 6, flexShrink: 0,
        background: rank === 1 ? "rgba(200,169,110,.15)" : "var(--el)",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 10, fontWeight: 600,
        color: rank === 1 ? "var(--gold)" : "var(--mut)",
        marginTop: 1,
      }}>#{rank}</div>

      {/* Infos */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 12, fontWeight: 500, color: "var(--txt)",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          marginBottom: 3,
        }}>
          {listing.title}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: 10, color: "var(--mut)", display: "flex", alignItems: "center", gap: 3 }}>
            <MapPin size={9} />{listing.city}
          </span>
          <span style={{ fontSize: 10, color: "var(--mut)", textTransform: "capitalize" }}>
            {listing.property_type?.replace("_", " ")}
          </span>
          {listing.surface > 0 && (
            <span style={{ fontSize: 10, color: "var(--mut)" }}>{listing.surface} m²</span>
          )}
        </div>

        {/* Raisons (matching) ou delta (similaires) */}
        {listing.match_reasons?.length > 0 && (
          <div style={{ display: "flex", gap: 4, marginTop: 5, flexWrap: "wrap" }}>
            {listing.match_reasons.slice(0, 2).map((r: string, i: number) => (
              <span key={i} style={{
                fontSize: 9, padding: "2px 6px", borderRadius: 999,
                background: "rgba(200,169,110,.10)", color: "var(--gold)",
                border: "1px solid rgba(200,169,110,.18)",
              }}>{r}</span>
            ))}
          </div>
        )}
        {listing.price_diff_pct !== undefined && (
          <div style={{ fontSize: 10, marginTop: 4, color: listing.price_diff_pct < 0 ? "var(--ok)" : "var(--mut)" }}>
            {listing.price_diff_pct < 0
              ? `↓ ${Math.abs(listing.price_diff_pct)}% moins cher`
              : listing.price_diff_pct > 0
                ? `↑ ${listing.price_diff_pct}% plus cher`
                : "Prix identique"}
          </div>
        )}
      </div>

      {/* Prix + score */}
      <div style={{ textAlign: "right", flexShrink: 0 }}>
        <div style={{
          fontFamily: "var(--font-display)", fontSize: 14, fontWeight: 600,
          color: "var(--gold)", marginBottom: 4,
        }}>
          {(listing.price / 1000).toFixed(0)}K
        </div>
        <ScoreBadge score={listing[scoreKey]} color={scoreColor} />
        <div style={{ fontSize: 9, color: "var(--mut)", marginTop: 2 }}>{scoreLabel}</div>
      </div>
    </div>
  );
}

function InvestCard({ zone, rank }: { zone: InvestZone; rank: number }) {
  const [expanded, setExpanded] = useState(false);
  const color = IC(zone.level);
  return (
    <div style={{ padding: "12px 0", borderBottom: "1px solid var(--bor)" }}>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start", cursor: "pointer" }}
        onClick={() => setExpanded(e => !e)}>
        <div style={{
          width: 22, height: 22, borderRadius: 6, flexShrink: 0,
          background: rank === 1 ? "rgba(82,200,150,.12)" : "var(--el)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 10, fontWeight: 600, color: rank === 1 ? "var(--ok)" : "var(--mut)", marginTop: 1,
        }}>#{rank}</div>

        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
            <span style={{ fontSize: 12, fontWeight: 500 }}>{zone.city}</span>
            <span style={{
              fontSize: 9, padding: "1px 6px", borderRadius: 999,
              background: `${color}14`, color, border: `1px solid ${color}28`,
            }}>{zone.level}</span>
          </div>
          <div style={{ fontSize: 10, color: "var(--mut)" }}>
            Croissance {zone.growth_rate_pct}%/an · {zone.horizon_years}
          </div>
        </div>

        <div style={{ textAlign: "right", flexShrink: 0 }}>
          <ScoreBadge score={zone.investment_score} color={color} />
          <div style={{ fontSize: 9, color: "var(--mut)", marginTop: 2 }}>potentiel</div>
        </div>
      </div>

      {expanded && (
        <div className="animate-fadeup" style={{
          marginTop: 10, marginLeft: 34,
          background: "var(--el)", borderRadius: 8, padding: "10px 12px",
        }}>
          <p style={{ fontSize: 11, color: "var(--txt)", lineHeight: 1.6, marginBottom: 8 }}>
            {zone.rationale}
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
            {[
              { label: "Demande",      val: `${(zone.demand_pressure * 100).toFixed(0)}%` },
              { label: "Infra",        val: zone.avg_ppm2 ? `${zone.avg_ppm2.toLocaleString("fr-FR")} TND/m²` : "N/A" },
              { label: "Recommandé",   val: zone.recommended_type.split("(")[0].trim() },
            ].map(k => (
              <div key={k.label} style={{ textAlign: "center" }}>
                <div style={{ fontSize: 10, color: "var(--mut)", marginBottom: 2 }}>{k.label}</div>
                <div style={{ fontSize: 11, fontWeight: 500, color: "var(--txt)" }}>{k.val}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Panneau de configuration ──────────────────────────────────────────────────

interface ConfigPanelProps {
  params: { budget: number; surface_min: number; city: string; property_type: string; risk_tolerance: string };
  onChange: (p: ConfigPanelProps["params"]) => void;
  onClose: () => void;
  onApply: () => void;
}

function ConfigPanel({ params, onChange, onClose, onApply }: ConfigPanelProps) {
  const [local, setLocal] = useState({ ...params });
  const up = (k: string, v: string | number) => setLocal(p => ({ ...p, [k]: v }));

  return (
    <div className="animate-fadeup" style={{
      position: "absolute", top: 48, right: 0, zIndex: 20,
      background: "var(--card)", border: "1px solid var(--gbor)",
      borderRadius: 12, padding: 20, width: 300,
      boxShadow: "0 8px 32px rgba(0,0,0,.5)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <span style={{ fontSize: 12, fontWeight: 500 }}>Personnaliser les recommandations</span>
        <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--mut)", padding: 2 }}>
          <X size={14} />
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div>
          <label style={{ fontSize: 10, color: "var(--mut)", textTransform: "uppercase", letterSpacing: ".06em", display: "block", marginBottom: 5 }}>
            Budget max (TND)
          </label>
          <input type="number" value={local.budget} onChange={e => up("budget", Number(e.target.value))}
            style={{ padding: "7px 10px", fontSize: 12 }} />
        </div>
        <div>
          <label style={{ fontSize: 10, color: "var(--mut)", textTransform: "uppercase", letterSpacing: ".06em", display: "block", marginBottom: 5 }}>
            Surface min (m²)
          </label>
          <input type="number" value={local.surface_min} onChange={e => up("surface_min", Number(e.target.value))}
            style={{ padding: "7px 10px", fontSize: 12 }} />
        </div>
        <div>
          <label style={{ fontSize: 10, color: "var(--mut)", textTransform: "uppercase", letterSpacing: ".06em", display: "block", marginBottom: 5 }}>
            Ville (optionnel)
          </label>
          <input value={local.city} onChange={e => up("city", e.target.value)} placeholder="Ex: Tunis"
            style={{ padding: "7px 10px", fontSize: 12 }} />
        </div>
        <div>
          <label style={{ fontSize: 10, color: "var(--mut)", textTransform: "uppercase", letterSpacing: ".06em", display: "block", marginBottom: 5 }}>
            Tolérance au risque
          </label>
          <select value={local.risk_tolerance} onChange={e => up("risk_tolerance", e.target.value)}
            style={{ padding: "7px 10px", fontSize: 12 }}>
            <option value="low">Faible — sécurité maximale</option>
            <option value="medium">Moyen — équilibré</option>
            <option value="high">Élevé — rendement maximal</option>
          </select>
        </div>

        <button className="btn-gold" onClick={() => { onChange(local); onApply(); onClose(); }}
          style={{ marginTop: 4, padding: "9px 0", fontSize: 12 }}>
          Appliquer
        </button>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// WIDGET PRINCIPAL
// ══════════════════════════════════════════════════════════════════════════════

const TABS = [
  { id: "matching",       label: "Pour vous",     Icon: Target      },
  { id: "similaires",     label: "Similaires",    Icon: Sparkles    },
  { id: "investissement", label: "Investissement",Icon: TrendingUp  },
];

// Données de démo si le backend n'est pas disponible
const DEMO_DATA: RecoData = {
  params: { budget: 350000, surface_min: 80, city: "Toutes", property_type: "Tous", risk_tolerance: "medium" },
  matching: [
    { title:"Appartement S+3 La Marsa", city:"La Marsa", property_type:"appartement", price:315000, surface:120, price_per_m2:2625, trust_score:0.84, legal_risk_score:0.12, match_score:0.88, match_reasons:["Dans votre budget idéal","Surface suffisante","Annonce fiable"] },
    { title:"Villa S+4 Nabeul",          city:"Nabeul",   property_type:"villa",        price:290000, surface:180, price_per_m2:1611, trust_score:0.77, legal_risk_score:0.18, match_score:0.81, match_reasons:["Prix/m² compétitif","Surface suffisante"] },
    { title:"Appartement S+2 Sousse",    city:"Sousse",   property_type:"appartement",  price:210000, surface:95,  price_per_m2:2210, trust_score:0.71, legal_risk_score:0.22, match_score:0.74, match_reasons:["Dans votre budget idéal","Annonce fiable"] },
  ],
  similaires: [
    { title:"Appartement S+3 Marsa",  city:"La Marsa", property_type:"appartement", price:325000, surface:118, price_per_m2:2754, trust_score:0.81, similarity_score:0.91, price_diff_pct:3.2 },
    { title:"Appt vue mer Carthage",  city:"Carthage", property_type:"appartement", price:305000, surface:115, price_per_m2:2652, trust_score:0.73, similarity_score:0.84, price_diff_pct:-3.2 },
    { title:"S+3 Ariana Soghra",      city:"Ariana",   property_type:"appartement", price:290000, surface:108, price_per_m2:2685, trust_score:0.79, similarity_score:0.79, price_diff_pct:-7.9 },
  ],
  investissement: [
    { city:"Hammamet",  investment_score:0.81, level:"Excellent", growth_rate_pct:7.5, demand_pressure:0.90, risk_score:0.20, avg_ppm2:3900, n_listings:1203, rationale:"Zone côtière premium. Valorisation soutenue par le tourisme international.", recommended_type:"villa (clientèle touristique)", horizon_years:"Court terme (1–3 ans)" },
    { city:"Nabeul",    investment_score:0.76, level:"Excellent", growth_rate_pct:7.1, demand_pressure:0.88, risk_score:0.18, avg_ppm2:2600, n_listings:654,  rationale:"Demande touristique + résidentielle en forte hausse. Proximité avec Hammamet.", recommended_type:"terrain (plus-value à terme)", horizon_years:"Court terme (1–3 ans)" },
    { city:"Sousse",    investment_score:0.72, level:"Bon",       growth_rate_pct:6.8, demand_pressure:0.83, risk_score:0.19, avg_ppm2:2800, n_listings:1098, rationale:"2ème pôle économique. Infrastructure solide, marché locatif actif.", recommended_type:"appartement (rendement locatif)", horizon_years:"Moyen terme (3–5 ans)" },
    { city:"Monastir",  investment_score:0.68, level:"Bon",       growth_rate_pct:6.4, demand_pressure:0.79, risk_score:0.21, avg_ppm2:2600, n_listings:743,  rationale:"Aéroport international + expansion résidentielle. Bon rendement locatif.", recommended_type:"appartement (rendement locatif)", horizon_years:"Moyen terme (3–5 ans)" },
    { city:"Mahdia",    investment_score:0.61, level:"Bon",       growth_rate_pct:5.9, demand_pressure:0.70, risk_score:0.24, avg_ppm2:1800, n_listings:312,  rationale:"Sous-évalué vs Sousse. Fort potentiel de rattrapage en 3-5 ans.", recommended_type:"villa (clientèle touristique)", horizon_years:"Moyen terme (3–5 ans)" },
  ],
};

export function RecommendationsWidget() {
  const [tab,      setTab]      = useState<"matching"|"similaires"|"investissement">("matching");
  const [data,     setData]     = useState<RecoData>(DEMO_DATA);
  const [loading,  setLoading]  = useState(false);
  const [showConf, setShowConf] = useState(false);
  const [params,   setParams]   = useState(DEMO_DATA.params);

  const load = useCallback(async (p = params) => {
    setLoading(true);
    try {
      const qs = new URLSearchParams({
        budget:         String(p.budget),
        surface_min:    String(p.surface_min),
        city:           p.city === "Toutes" ? "" : p.city,
        property_type:  p.property_type === "Tous" ? "" : p.property_type,
        risk_tolerance: p.risk_tolerance,
      });
      const r = await fetch(`/api/recommendations?${qs}`);
      if (r.ok) setData(await r.json());
    } catch {
      // garde les données de démo
    }
    setLoading(false);
  }, [params]);

  useEffect(() => { load(); }, []);

  const currentData =
    tab === "matching"       ? data.matching       :
    tab === "similaires"     ? data.similaires      :
                               data.investissement;

  return (
    <div style={{ position: "relative" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--gold)", flexShrink: 0 }} />
          <span style={{ fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 600 }}>
            Recommandations du jour
          </span>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button onClick={() => load()} disabled={loading} style={{
            display: "flex", alignItems: "center", gap: 5,
            padding: "5px 10px", borderRadius: 7, border: "1px solid var(--bor)",
            background: "transparent", color: "var(--mut)", fontSize: 11,
            fontFamily: "var(--font-body)", cursor: loading ? "not-allowed" : "pointer",
          }}>
            <RefreshCw size={11} className={loading ? "animate-spin" : ""} />
            {loading ? "..." : "Rafraîchir"}
          </button>
          <button onClick={() => setShowConf(s => !s)} style={{
            display: "flex", alignItems: "center", gap: 5,
            padding: "5px 10px", borderRadius: 7,
            border: `1px solid ${showConf ? "var(--gbor)" : "var(--bor)"}`,
            background: showConf ? "var(--gdim)" : "transparent",
            color: showConf ? "var(--gold)" : "var(--mut)",
            fontSize: 11, fontFamily: "var(--font-body)", cursor: "pointer",
          }}>
            <SlidersHorizontal size={11} />
            Profil
          </button>
        </div>
      </div>

      {/* Panel config */}
      {showConf && (
        <ConfigPanel
          params={params}
          onChange={setParams}
          onClose={() => setShowConf(false)}
          onApply={() => load(params)}
        />
      )}

      {/* Résumé profil actif */}
      <div style={{
        display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap",
      }}>
        {[
          { label: `Budget ${(params.budget/1000).toFixed(0)}K TND` },
          { label: `≥ ${params.surface_min} m²` },
          { label: params.city !== "Toutes" ? params.city : "Toutes villes" },
          { label: `Risque ${params.risk_tolerance}` },
        ].map((b, i) => (
          <span key={i} style={{
            fontSize: 10, padding: "2px 8px", borderRadius: 999,
            background: "var(--el)", color: "var(--mut)",
            border: "1px solid var(--bor)",
          }}>{b.label}</span>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 14, background: "var(--el)", padding: 4, borderRadius: 9, border: "1px solid var(--bor)" }}>
        {TABS.map(({ id, label, Icon }) => (
          <button key={id} onClick={() => setTab(id as typeof tab)} style={{
            flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 5,
            padding: "6px 0", borderRadius: 6, border: "none", cursor: "pointer",
            fontSize: 11, fontFamily: "var(--font-body)",
            background: tab === id ? "var(--card)" : "transparent",
            color:      tab === id ? "var(--gold)"  : "var(--mut)",
            transition: "all .15s",
          }}>
            <Icon size={11} />{label}
          </button>
        ))}
      </div>

      {/* Contenu */}
      {loading ? (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200 }}>
          <div className="animate-spin" style={{ width: 28, height: 28, border: "2px solid var(--gbor)", borderTop: "2px solid var(--gold)", borderRadius: "50%" }} />
        </div>
      ) : currentData.length === 0 ? (
        <div style={{ textAlign: "center", padding: "32px 0", color: "var(--mut)", fontSize: 12 }}>
          Aucune recommandation pour ce profil. Ajustez vos critères.
        </div>
      ) : (
        <div>
          {tab === "matching" && (data.matching as MatchedListing[]).map((l, i) => (
            <ListingCard key={i} listing={l} rank={i+1}
              scoreKey="match_score" scoreLabel="match" scoreColor="var(--gold)" />
          ))}
          {tab === "similaires" && (data.similaires as SimilarListing[]).map((l, i) => (
            <ListingCard key={i} listing={l} rank={i+1}
              scoreKey="similarity_score" scoreLabel="similarité" scoreColor="var(--info)" />
          ))}
          {tab === "investissement" && (data.investissement as InvestZone[]).map((z, i) => (
            <InvestCard key={z.city} zone={z} rank={i+1} />
          ))}
        </div>
      )}

      {/* Footer */}
      <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid var(--bor)", display: "flex", justifyContent: "flex-end" }}>
        <button style={{ display: "flex", alignItems: "center", gap: 4, background: "none", border: "none", color: "var(--gold)", fontSize: 11, cursor: "pointer", fontFamily: "var(--font-body)" }}>
          Voir toutes les recommandations <ChevronRight size={11} />
        </button>
      </div>
    </div>
  );
}
