"use client";

import { useEffect, useState, useCallback } from "react";
import {
  TrendingUp, TrendingDown, Minus, MapPin,
  AlertTriangle, Bell, BarChart2, RefreshCw,
  ChevronRight, Clock, CheckCircle,
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell,
} from "recharts";

// ── Types ─────────────────────────────────────────────────────────────────────
interface ZoneAlert {
  zone: string; zone_type: string; alert_type: string;
  severity: "critical"|"high"|"medium";
  price_growth: number|null; volume_growth: number|null;
  emergence_score: number;
  n_listings_recent: number; n_listings_previous: number;
  median_price_recent: number|null; median_price_previous: number|null;
  message: string;
  recommendation: string;
  action_horizon_days: number;
}

interface TSPoint { period: string; median_price: number|null; volume: number; }
interface SpatialZone { n_listings: number; median_ppm2: number|null; lat: number|null; lon: number|null; }

// ── Helpers ───────────────────────────────────────────────────────────────────
const SEV_COLOR = (s: string) =>
  s === "critical" ? "#E05C5C" : s === "high" ? "#E8A84C" : "#6B9FE8";

const ALERT_LABEL: Record<string, string> = {
  emerging: "Zone émergente", price_surge: "Hausse de prix",
  volume_surge: "Hausse de volume", declining: "Zone en déclin",
};

const ALERT_ICON: Record<string, string> = {
  emerging: "🚀", price_surge: "📈", volume_surge: "📊", declining: "📉",
};

const HORIZON_LABEL = (days: number) =>
  days <= 30 ? "Agir sous 30 jours" :
  days <= 45 ? "Agir sous 45 jours" :
  days <= 90 ? "Agir sous 3 mois"   : "Horizon long terme";

// ── Données démo ──────────────────────────────────────────────────────────────
const DEMO_ALERTS: ZoneAlert[] = [
  {
    zone:"Hammamet", zone_type:"city", alert_type:"emerging", severity:"critical",
    price_growth:0.152, volume_growth:0.284, emergence_score:0.82,
    n_listings_recent:142, n_listings_previous:88,
    median_price_recent:380000, median_price_previous:330000,
    message:"Zone émergente : Hammamet — prix +15.2% et volume +28.4%.",
    recommendation:"Zone à fort potentiel : Hammamet enregistre une hausse simultanée des prix (+15.2%) et du volume (+28.4%). Fenêtre d'opportunité estimée à 30-60 jours avant alignement sur les prix des zones voisines. Recommandé pour achat ou investissement locatif.",
    action_horizon_days:30,
  },
  {
    zone:"Nabeul", zone_type:"city", alert_type:"price_surge", severity:"high",
    price_growth:0.122, volume_growth:0.081, emergence_score:0.63,
    n_listings_recent:98, n_listings_previous:72,
    median_price_recent:220000, median_price_previous:196000,
    message:"Hausse de prix à Nabeul : +12.2%.",
    recommendation:"Hausse de prix marquée à Nabeul (+12.2%) sans hausse de volume correspondante. Possible tension de l'offre. Si budget disponible, agir sous 45 jours. Sinon, envisager des zones alternatives : Hammamet, Kélibia.",
    action_horizon_days:45,
  },
  {
    zone:"Mahdia", zone_type:"city", alert_type:"volume_surge", severity:"medium",
    price_growth:0.041, volume_growth:0.312, emergence_score:0.44,
    n_listings_recent:61, n_listings_previous:47,
    median_price_recent:165000, median_price_previous:158000,
    message:"Forte activité à Mahdia : 61 annonces (+31.2%).",
    recommendation:"Fort regain d'activité à Mahdia (+31.2% d'annonces). Signal d'attractivité croissante. Prix encore stables : opportunité à court terme pour acheteurs et investisseurs.",
    action_horizon_days:60,
  },
  {
    zone:"Kasserine", zone_type:"city", alert_type:"declining", severity:"medium",
    price_growth:-0.093, volume_growth:-0.152, emergence_score:0.32,
    n_listings_recent:18, n_listings_previous:32,
    median_price_recent:85000, median_price_previous:93000,
    message:"Zone en déclin : Kasserine — baisse de 9.3%.",
    recommendation:"Zone en déclin à Kasserine (-9.3% de prix). Déconseillé pour investissement à court terme. Pour acheteurs résidentiels uniquement avec horizon > 5 ans.",
    action_horizon_days:180,
  },
];

const DEMO_TS: TSPoint[] = [
  {period:"2025-09",median_price:290000,volume:412},{period:"2025-10",median_price:295000,volume:441},
  {period:"2025-11",median_price:300000,volume:388},{period:"2025-12",median_price:298000,volume:356},
  {period:"2026-01",median_price:305000,volume:502},{period:"2026-02",median_price:314000,volume:534},
];

const DEMO_SPATIAL: [string, SpatialZone][] = [
  ["Tunis",    {n_listings:1842,median_ppm2:2800,lat:36.81,lon:10.18}],
  ["Sousse",   {n_listings:1103,median_ppm2:2450,lat:35.83,lon:10.64}],
  ["Nabeul",   {n_listings:874, median_ppm2:2200,lat:36.45,lon:10.73}],
  ["Hammamet", {n_listings:742, median_ppm2:3800,lat:36.40,lon:10.61}],
  ["Sfax",     {n_listings:631, median_ppm2:1950,lat:34.74,lon:10.76}],
  ["Monastir", {n_listings:518, median_ppm2:2350,lat:35.77,lon:10.83}],
  ["Mahdia",   {n_listings:312, median_ppm2:1650,lat:35.50,lon:11.06}],
  ["Bizerte",  {n_listings:287, median_ppm2:1480,lat:37.27,lon:9.87 }],
];

// ── Composants ────────────────────────────────────────────────────────────────

function AlertCard({ alert, expanded, onToggle }: {
  alert: ZoneAlert;
  expanded: boolean;
  onToggle: () => void;
}) {
  const color = SEV_COLOR(alert.severity);
  return (
    <div style={{
      background:`${color}08`, border:`1px solid ${color}28`,
      borderRadius:10, marginBottom:10, overflow:"hidden",
      cursor:"pointer",
    }} onClick={onToggle}>
      {/* Header */}
      <div style={{ padding:"12px 16px", display:"flex", justifyContent:"space-between", alignItems:"flex-start" }}>
        <div style={{ display:"flex", alignItems:"center", gap:8, flex:1 }}>
          <span style={{ fontSize:16 }}>{ALERT_ICON[alert.alert_type]}</span>
          <div style={{ flex:1 }}>
            <div style={{ display:"flex", alignItems:"center", gap:6, flexWrap:"wrap" }}>
              <span style={{ fontSize:13, fontWeight:500, color }}>{alert.zone}</span>
              <span style={{
                fontSize:9, padding:"2px 7px", borderRadius:999,
                background:`${color}14`, color, border:`1px solid ${color}22`,
              }}>{ALERT_LABEL[alert.alert_type]}</span>
              <span style={{
                fontSize:9, padding:"2px 7px", borderRadius:999,
                background:`${color}14`, color, textTransform:"capitalize",
              }}>{alert.severity}</span>
            </div>
            <p style={{ fontSize:11, color:"var(--mut)", marginTop:3 }}>{alert.message}</p>
          </div>
        </div>
        <div style={{ display:"flex", alignItems:"center", gap:8, flexShrink:0, marginLeft:8 }}>
          <div style={{ textAlign:"right" }}>
            <div style={{ fontFamily:"var(--font-display)", fontSize:16, fontWeight:600, color }}>
              {(alert.emergence_score*100).toFixed(0)}
            </div>
            <div style={{ fontSize:9, color:"var(--mut)" }}>score</div>
          </div>
          <ChevronRight size={14} color="var(--mut)"
            style={{ transform: expanded ? "rotate(90deg)" : "none", transition:"transform .2s" }} />
        </div>
      </div>

      {/* Métriques rapides */}
      <div style={{ paddingInline:16, paddingBottom:12, display:"flex", gap:12 }}>
        {alert.price_growth !== null && (
          <span style={{ fontSize:11, color:"var(--mut)" }}>
            Prix : <b style={{ color: alert.price_growth > 0 ? "#52C896" : "#E05C5C" }}>
              {alert.price_growth > 0 ? "+" : ""}{(alert.price_growth*100).toFixed(1)}%
            </b>
          </span>
        )}
        {alert.volume_growth !== null && (
          <span style={{ fontSize:11, color:"var(--mut)" }}>
            Volume : <b style={{ color: alert.volume_growth > 0 ? "#52C896" : "#E05C5C" }}>
              {alert.volume_growth > 0 ? "+" : ""}{(alert.volume_growth*100).toFixed(1)}%
            </b>
          </span>
        )}
        {alert.median_price_recent && (
          <span style={{ fontSize:11, color:"var(--mut)" }}>
            Prix médian : <b style={{ color:"var(--gold)" }}>
              {alert.median_price_recent.toLocaleString("fr-TN")} TND
            </b>
          </span>
        )}
      </div>

      {/* Recommandation actionnable (expandable) */}
      {expanded && (
        <div style={{
          borderTop:`1px solid ${color}20`,
          padding:"12px 16px",
          background:`${color}06`,
        }}>
          <div style={{ display:"flex", gap:8, marginBottom:8 }}>
            <CheckCircle size={14} color={color} style={{ flexShrink:0, marginTop:1 }} />
            <div>
              <div style={{ fontSize:11, fontWeight:500, color, marginBottom:4 }}>
                Recommandation
              </div>
              <p style={{ fontSize:12, color:"var(--txt)", lineHeight:1.6 }}>
                {alert.recommendation}
              </p>
            </div>
          </div>
          <div style={{ display:"flex", alignItems:"center", gap:6, marginTop:10 }}>
            <Clock size={11} color="var(--mut)" />
            <span style={{
              fontSize:10, padding:"2px 9px", borderRadius:999,
              background:`${color}14`, color, border:`1px solid ${color}22`,
            }}>
              {HORIZON_LABEL(alert.action_horizon_days)}
            </span>
            <span style={{ fontSize:10, color:"var(--mut)" }}>
              · Horizon {alert.action_horizon_days} jours
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// PAGE PRINCIPALE
// ══════════════════════════════════════════════════════════════════════════════

export default function TerritoirePage() {
  const [alerts,     setAlerts]     = useState<ZoneAlert[]>(DEMO_ALERTS);
  const [tsData,     setTsData]     = useState<TSPoint[]>(DEMO_TS);
  const [spatial,    setSpatial]    = useState<[string, SpatialZone][]>(DEMO_SPATIAL);
  const [loading,    setLoading]    = useState(false);
  const [filter,     setFilter]     = useState<"all"|"critical"|"high"|"medium">("all");
  const [expandedId, setExpandedId] = useState<string|null>(null);
  const [mkStats,    setMkStats]    = useState<Record<string, any>>({});
  const [lastUpdated,setLastUpdated]= useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Alertes DSO3
      const ra = await fetch("/api/territorial/alerts");
      if (ra.ok) {
        const d = await ra.json();
        if (d.alerts?.length) setAlerts(d.alerts);
      }
      // Séries temporelles DSO1
      const rt = await fetch("/api/territorial/time-series?group_by=city&freq=M");
      if (rt.ok) {
        const d = await rt.json();
        if (d.global?.length) setTsData(d.global);
        // Récupère les stats Mann-Kendall
        if (d.trends) setMkStats(d.trends);
      }
      // Spatial DSO2
      const rs = await fetch("/api/territorial/spatial?level=city");
      if (rs.ok) {
        const d = await rs.json();
        if (d.by_city) {
          const sorted = Object.entries(d.by_city as Record<string, SpatialZone>)
            .sort((a, b) => (b[1].median_ppm2||0) - (a[1].median_ppm2||0))
            .slice(0, 8);
          setSpatial(sorted as [string, SpatialZone][]);
        }
      }
      setLastUpdated(new Date().toLocaleTimeString("fr-FR"));
    } catch { /* garde les données démo */ }
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, []);

  const filteredAlerts = filter === "all" ? alerts : alerts.filter(a => a.severity === filter);
  const nCritical = alerts.filter(a => a.severity === "critical").length;
  const nHigh     = alerts.filter(a => a.severity === "high").length;
  const nEmerging = alerts.filter(a => ["emerging","price_surge","volume_surge"].includes(a.alert_type)).length;

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:20 }}>
      {/* Header */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start" }}>
        <div>
          <h1 style={{ fontFamily:"var(--font-display)", fontSize:22, fontWeight:600, marginBottom:4 }}>
            Dynamiques territoriales
          </h1>
          <p style={{ fontSize:13, color:"var(--mut)" }}>
            BO2 — Séries temporelles · Agrégation spatiale · Zones émergentes
            {lastUpdated && <span style={{ marginLeft:8, fontSize:11 }}>· {lastUpdated}</span>}
          </p>
        </div>
        <button onClick={loadData} disabled={loading} style={{
          display:"flex", alignItems:"center", gap:6,
          padding:"8px 14px", borderRadius:8, border:"1px solid var(--bor)",
          background:"transparent", color:"var(--mut)",
          fontSize:12, cursor: loading ? "not-allowed" : "pointer",
          fontFamily:"var(--font-body)",
        }}>
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          {loading ? "Chargement..." : "Actualiser"}
        </button>
      </div>

      {/* KPIs */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:14 }}>
        {[
          {label:"Alertes critiques",  val:nCritical,     color:"var(--bad)"  },
          {label:"Alertes importantes",val:nHigh,         color:"var(--warn)" },
          {label:"Zones émergentes",   val:nEmerging,     color:"var(--ok)"   },
          {label:"Total alertes",      val:alerts.length, color:"var(--gold)" },
        ].map(k => (
          <div key={k.label} className="card" style={{ padding:"18px 20px" }}>
            <div style={{ fontFamily:"var(--font-display)", fontSize:28, fontWeight:600, color:k.color }}>
              {k.val}
            </div>
            <div style={{ fontSize:11, color:"var(--mut)", marginTop:3 }}>{k.label}</div>
          </div>
        ))}
      </div>

      {/* Contenu 2 colonnes */}
      <div style={{ display:"grid", gridTemplateColumns:"1fr 400px", gap:16, alignItems:"start" }}>

        {/* Colonne gauche */}
        <div style={{ display:"flex", flexDirection:"column", gap:16 }}>

          {/* Série temporelle nationale */}
          <div className="card" style={{ padding:22 }}>
            <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:16 }}>
              <BarChart2 size={14} color="var(--gold)" />
              <span style={{ fontFamily:"var(--font-display)", fontSize:14, fontWeight:600 }}>
                Évolution mensuelle — marché national
              </span>
              <span style={{ fontSize:10, color:"var(--mut)", marginLeft:"auto" }}>
                Méthode : Mann-Kendall + régression linéaire
              </span>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={tsData}>
                <XAxis dataKey="period" tick={{fontSize:10,fill:"var(--mut)"}} axisLine={false} tickLine={false}/>
                <YAxis yAxisId="price" orientation="left" tick={{fontSize:10,fill:"var(--mut)"}}
                  axisLine={false} tickLine={false} tickFormatter={v=>`${(v/1000).toFixed(0)}K`}/>
                <YAxis yAxisId="vol" orientation="right" tick={{fontSize:10,fill:"var(--mut)"}}
                  axisLine={false} tickLine={false}/>
                <Tooltip contentStyle={{background:"var(--el)",border:"1px solid var(--bor)",borderRadius:8,fontSize:11}}
                  formatter={(v:number,n:string)=>n==="median_price"?[`${v.toLocaleString("fr-TN")} TND`,"Prix médian"]:[v,"Volume"]}/>
                <Line yAxisId="price" type="monotone" dataKey="median_price" stroke="var(--gold)" strokeWidth={2} dot={false}/>
                <Line yAxisId="vol"   type="monotone" dataKey="volume" stroke="var(--info)" strokeWidth={1.5} dot={false} strokeDasharray="4 2"/>
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Prix/m² par ville */}
          <div className="card" style={{ padding:22 }}>
            <div style={{ fontFamily:"var(--font-display)", fontSize:14, fontWeight:600, marginBottom:14 }}>
              Prix/m² médian par ville (top 8)
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={spatial.map(([z,s])=>({zone:z,ppm2:s.median_ppm2||0}))} layout="vertical">
                <XAxis type="number" tick={{fontSize:10,fill:"var(--mut)"}} axisLine={false} tickLine={false}/>
                <YAxis dataKey="zone" type="category" tick={{fontSize:11,fill:"var(--txt)"}}
                  axisLine={false} tickLine={false} width={80}/>
                <Tooltip contentStyle={{background:"var(--el)",border:"1px solid var(--bor)",borderRadius:8,fontSize:11}}
                  formatter={(v:number)=>[`${v.toLocaleString("fr-TN")} TND/m²`,"Prix/m²"]}/>
                <Bar dataKey="ppm2" radius={[0,4,4,0]}>
                  {spatial.map(([,s],i)=>(
                    <Cell key={i} fill={
                      (s.median_ppm2||0)>3000?"#E05C5C":(s.median_ppm2||0)>2000?"#E8A84C":"#52C896"
                    }/>
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Note méthodologique */}
          <div style={{
            background:"var(--el)", border:"1px solid var(--bor)",
            borderRadius:8, padding:"12px 16px", fontSize:11, color:"var(--mut)",
            lineHeight:1.6,
          }}>
            <b style={{ color:"var(--txt)" }}>Méthodologie :</b> Les tendances sont détectées via le test de
            Mann-Kendall (non-paramétrique, α=0.05) combiné à une régression linéaire.
            Une tendance est reportée comme significative seulement si p &lt; 0.05.
            Seuils d'alerte : prix +8% (≈1.6σ), volume +20%. Voir{" "}
            <code style={{ fontSize:10, background:"rgba(255,255,255,.05)", padding:"1px 4px", borderRadius:3 }}>
              docs/methodology.md
            </code>
          </div>
        </div>

        {/* Colonne droite — alertes avec recommandations */}
        <div className="card" style={{ padding:22, position:"sticky", top:72 }}>
          <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:14 }}>
            <Bell size={14} color="#E05C5C" />
            <span style={{ fontFamily:"var(--font-display)", fontSize:14, fontWeight:600 }}>
              Alertes & Recommandations
            </span>
          </div>
          <p style={{ fontSize:11, color:"var(--mut)", marginBottom:14, lineHeight:1.5 }}>
            Cliquez sur une alerte pour voir la recommandation actionnable et l'horizon d'action.
          </p>

          {/* Filtres */}
          <div style={{
            display:"flex", gap:3, marginBottom:14, background:"var(--el)",
            padding:3, borderRadius:8, border:"1px solid var(--bor)",
          }}>
            {(["all","critical","high","medium"] as const).map(f => (
              <button key={f} onClick={() => setFilter(f)} style={{
                flex:1, padding:"5px 0", borderRadius:5, border:"none",
                cursor:"pointer", fontSize:10, fontFamily:"var(--font-body)",
                background: filter===f ? "var(--card)" : "transparent",
                color:      filter===f ? "var(--gold)" : "var(--mut)",
              }}>
                {f==="all"?"Toutes":f.charAt(0).toUpperCase()+f.slice(1)}
              </button>
            ))}
          </div>

          <div style={{ maxHeight:620, overflowY:"auto" }}>
            {filteredAlerts.length === 0 ? (
              <div style={{ textAlign:"center", padding:"24px 0", color:"var(--mut)", fontSize:12 }}>
                Aucune alerte pour ce filtre
              </div>
            ) : filteredAlerts.map((alert, i) => (
              <AlertCard
                key={`${alert.zone}-${i}`}
                alert={alert}
                expanded={expandedId === `${alert.zone}-${i}`}
                onToggle={() => setExpandedId(
                  expandedId === `${alert.zone}-${i}` ? null : `${alert.zone}-${i}`
                )}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
