"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { Database, Activity, ShieldCheck, AlertTriangle, MapPin, Sparkles, RefreshCw, TrendingUp, TrendingDown } from "lucide-react";

// ── Données démo ──────────────────────────────────────────────────────────────
const FALLBACK = {
  total_raw:14927, total_clean:8412, avg_trust:0.673,
  suspect_count:1303, high_legal:412,
  recent:[
    {id:1,title:"Villa S+4 Hammamet Nord",   city:"Hammamet",type:"villa",       trust:.84,legal:.15,trust_level:"Fiable", legal_level:"Faible"},
    {id:2,title:"Terrain 800m² Nabeul",       city:"Nabeul",  type:"terrain",     trust:.31,legal:.72,trust_level:"Suspect",legal_level:"Élevé"},
    {id:3,title:"Appartement S+2 La Marsa",  city:"La Marsa",type:"appartement", trust:.71,legal:.28,trust_level:"Moyen",  legal_level:"Moyen"},
    {id:4,title:"Studio Centre Tunis",        city:"Tunis",   type:"studio",      trust:.89,legal:.09,trust_level:"Fiable", legal_level:"Faible"},
    {id:5,title:"Local commercial Sfax",      city:"Sfax",    type:"bureau_local",trust:.55,legal:.43,trust_level:"Moyen",  legal_level:"Moyen"},
  ],
};
const PREV        = {total_clean:8100, avg_trust:0.648, suspect_count:1420};
const TRUST_DIST  = [{l:"Fiable",n:4821,c:"#52C896"},{l:"Moyen",n:2288,c:"#E8A84C"},{l:"Suspect",n:1303,c:"#E05C5C"}];
const PROP_DIST   = [{name:"Appartement",v:38,c:"#C8A96E"},{name:"Villa",v:24,c:"#52C896"},{name:"Terrain",v:18,c:"#E8A84C"},{name:"Maison",v:12,c:"#6B9FE8"},{name:"Studio",v:8,c:"#A88EF0"}];
const DEMO_BO2    = [{zone:"Hammamet",alert_type:"emerging",price_growth:0.152},{zone:"Nabeul",alert_type:"price_surge",price_growth:0.122},{zone:"Mahdia",alert_type:"volume_surge",volume_growth:0.312}];
const INSIGHTS    = [
  "Aujourd'hui, 3 alertes territoriales actives. Hammamet poursuit sa hausse (+15.2%) — fenêtre d'opportunité de 30 jours. 8 412 annonces fiables. Trust score moyen en légère amélioration.",
  "Mahdia enregistre +31% de volume d'annonces sans hausse de prix — zone à surveiller. Grand Tunis concentre 42% du volume national. Aucun drift détecté.",
  "Sousse en zone émergente modérée. Pipeline toutes les 6h opérationnel. Qualité dataset : 82/100. Trust moyen 0.673 — marché réel, pas parfait.",
];
const ICONS: Record<string,string> = {emerging:"🚀",price_surge:"📈",volume_surge:"📊",declining:"📉"};
const LLC: Record<string,string>   = {"Faible":"#52C896","Moyen":"#E8A84C","Élevé":"#E05C5C"};
const TC  = (s:number) => s>=.75?"var(--ok)":s>=.5?"var(--warn)":"var(--bad)";

// ── KPI animé ──────────────────────────────────────────────────────────────────
function CounterKpi({ label, value, color="var(--gold)", sub, prev, higherIsBetter=true, decimals=0, icon }: {
  label:string; value:number; color?:string; sub?:string;
  prev?:number; higherIsBetter?:boolean; decimals?:number; icon?:React.ReactNode;
}) {
  const [displayed, setDisplayed] = useState(0);
  const frameRef = useRef<number|null>(null);
  const startRef = useRef<number|null>(null);

  useEffect(()=>{
    startRef.current = null;
    const animate = (ts:number) => {
      if (!startRef.current) startRef.current = ts;
      const progress = Math.min((ts - startRef.current) / 1200, 1);
      const eased    = 1 - Math.pow(1-progress, 3);
      setDisplayed(eased * value);
      if (progress < 1) frameRef.current = requestAnimationFrame(animate);
    };
    frameRef.current = requestAnimationFrame(animate);
    return ()=>{ if(frameRef.current) cancelAnimationFrame(frameRef.current); };
  }, [value]);

  const hasDelta = prev !== undefined;
  const delta    = hasDelta ? ((value - prev!) / Math.abs(prev!) * 100) : 0;
  const good     = higherIsBetter ? delta > 0 : delta < 0;
  const dc       = good ? "var(--ok)" : "var(--bad)";

  return (
    <div style={{ background:"var(--card)", border:"1px solid var(--bor)", borderRadius:12, padding:"18px 20px" }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start" }}>
        <div style={{ flex:1 }}>
          <div style={{ fontSize:10, color:"var(--mut)", textTransform:"uppercase", letterSpacing:".07em", marginBottom:6 }}>{label}</div>
          <div style={{ fontFamily:"var(--font-display)", fontSize:28, fontWeight:700, color, lineHeight:1 }}>
            {decimals>0 ? displayed.toFixed(decimals) : Math.round(displayed).toLocaleString("fr-FR")}
          </div>
          {hasDelta && (
            <div style={{ display:"flex", alignItems:"center", gap:3, fontSize:11, color:dc, marginTop:5 }}>
              {delta>0 ? <TrendingUp size={10}/> : <TrendingDown size={10}/>}
              <span style={{ fontWeight:500 }}>{delta>0?"+":""}{delta.toFixed(1)}%</span>
              <span style={{ color:"var(--mut)", fontSize:9 }}>vs précédent</span>
            </div>
          )}
          {sub && <div style={{ fontSize:10, color:"var(--mut)", marginTop:4 }}>{sub}</div>}
        </div>
        {icon && (
          <div style={{ width:36, height:36, borderRadius:9, background:`${color}12`, display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0 }}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// PAGE PRINCIPALE
// ══════════════════════════════════════════════════════════════════════════════
export default function DashboardPage() {
  // ── Tous les useRef/useState/useCallback DANS le composant ─────────────────
  const [stats,     setStats]     = useState<any>(FALLBACK);
  const [alerts,    setAlerts]    = useState<any[]>([]);
  const [insight,   setInsight]   = useState(INSIGHTS[0]);
  const [loading,   setLoading]   = useState(false);
  const [insLoading,setInsLoading]= useState(false);
  const [lastAt,    setLastAt]    = useState("");
  const firstRun  = useRef(true);
  const idxRef    = useRef(0);         // ← useRef ICI dans le composant, pas dehors !
  const interval  = useRef<any>(null);

  const loadInsight = useCallback(async (silent=false) => {
    if (!silent) setInsLoading(true);
    try {
      const r = await fetch("/api/insight");
      if (r.ok) { const d=await r.json(); setInsight(d.insight||INSIGHTS[idxRef.current%INSIGHTS.length]); }
      else { setInsight(INSIGHTS[idxRef.current%INSIGHTS.length]); idxRef.current++; }
    } catch { setInsight(INSIGHTS[idxRef.current%INSIGHTS.length]); idxRef.current++; }
    if (!silent) setInsLoading(false);
  }, []);

  const refresh = useCallback(async (silent=false) => {
    if (!silent) setLoading(true);
    firstRun.current = false;
    try {
      const r = await fetch("/api/dashboard");
      if (r.ok) setStats(await r.json());
    } catch {}
    try {
      const r2 = await fetch("/api/territorial/alerts?lookback_recent=45");
      if (r2.ok) { const d=await r2.json(); if(d?.alerts?.length) setAlerts(d.alerts.slice(0,3)); else setAlerts(DEMO_BO2); }
      else setAlerts(DEMO_BO2);
    } catch { setAlerts(DEMO_BO2); }
    setLastAt(new Date().toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit",second:"2-digit"}));
    if (!silent) setLoading(false);
  }, []);

  useEffect(()=>{
    loadInsight();
    refresh();
    interval.current = setInterval(()=>refresh(true), 60000);
    return ()=>clearInterval(interval.current);
  }, []);

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:20 }}>
      {/* Header */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start" }}>
        <div>
          <h1 style={{ fontFamily:"var(--font-display)", fontSize:24, fontWeight:600, marginBottom:4 }}>Vue d'ensemble</h1>
          <p style={{ fontSize:13, color:"var(--mut)" }}>Marché immobilier tunisien — Estate Mind PropTech</p>
        </div>
        <div style={{ display:"flex", alignItems:"center", gap:10 }}>
          {lastAt && <span style={{ fontSize:10, color:"var(--mut)" }}>Mis à jour {lastAt}</span>}
          <button onClick={()=>refresh()} disabled={loading} style={{
            display:"flex", alignItems:"center", gap:5, padding:"6px 12px",
            borderRadius:7, border:"1px solid var(--bor)", background:"transparent",
            color:"var(--mut)", fontSize:11, cursor:loading?"not-allowed":"pointer", fontFamily:"var(--font-body)",
          }}>
            <RefreshCw size={11} style={{ animation:loading?"spin 1s linear infinite":"none" }}/>
            {loading?"...":"Actualiser"}
          </button>
          <div style={{ display:"flex", alignItems:"center", gap:5 }}>
            <div style={{ width:6,height:6,borderRadius:"50%",background:"var(--ok)",animation:"pulse 2s ease-in-out infinite" }}/>
            <span style={{ fontSize:10, color:"var(--mut)" }}>Auto 60s</span>
          </div>
        </div>
      </div>

      {/* Insight du jour */}
      <div style={{ background:"linear-gradient(135deg,rgba(200,169,110,.08),rgba(127,119,221,.05))", border:"1px solid rgba(200,169,110,.25)", borderRadius:12, padding:"14px 18px" }}>
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8 }}>
          <div style={{ display:"flex", alignItems:"center", gap:7 }}>
            <div style={{ width:22,height:22,borderRadius:6,background:"rgba(200,169,110,.15)",display:"flex",alignItems:"center",justifyContent:"center" }}>
              <Sparkles size={11} color="var(--gold)"/>
            </div>
            <span style={{ fontSize:12, fontWeight:500, color:"var(--gold)" }}>Insight du jour</span>
          </div>
          <button onClick={()=>loadInsight()} style={{ background:"none",border:"none",cursor:"pointer",color:"var(--mut)",padding:2 }}>
            <RefreshCw size={10} style={{ animation:insLoading?"spin 1s linear infinite":"none" }}/>
          </button>
        </div>
        {insLoading
          ? <span style={{ fontSize:12,color:"var(--mut)" }}>Génération...</span>
          : <p style={{ fontSize:13,color:"var(--txt)",lineHeight:1.7,margin:0 }}>{insight}</p>
        }
      </div>

      {/* KPIs animés */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:14 }}>
        <CounterKpi label="Annonces brutes"    value={stats.total_raw}    color="var(--txt)"  sub="annonces_combined.csv"    icon={<Database   size={15} color="var(--txt)" />} />
        <CounterKpi label="Après nettoyage"    value={stats.total_clean}  color="var(--ok)"   sub={`${Math.round(stats.total_clean/Math.max(stats.total_raw,1)*100)}% conservées`} prev={PREV.total_clean}  higherIsBetter icon={<Activity    size={15} color="var(--ok)"  />} />
        <CounterKpi label="Trust score moyen"  value={stats.avg_trust}    color="var(--info)" sub="fiabilité globale"         prev={PREV.avg_trust}     higherIsBetter decimals={3} icon={<ShieldCheck size={15} color="var(--info)"/>} />
        <CounterKpi label="Annonces suspectes" value={stats.suspect_count} color="var(--bad)" sub="trust_score < 0.50"        prev={PREV.suspect_count} higherIsBetter={false}     icon={<AlertTriangle size={15} color="var(--bad)" />} />
      </div>

      {/* Main layout */}
      <div style={{ display:"grid", gridTemplateColumns:"1fr 370px", gap:14, alignItems:"start" }}>
        <div style={{ display:"flex", flexDirection:"column", gap:14 }}>
          {/* Charts */}
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14 }}>
            <div style={{ background:"var(--card)",border:"1px solid var(--bor)",borderRadius:12,padding:22 }}>
              <div style={{ fontSize:13,fontWeight:600,marginBottom:12 }}>Distribution Trust Score</div>
              <div style={{ display:"flex",gap:8,marginBottom:12 }}>
                {TRUST_DIST.map(d=>(
                  <div key={d.l} style={{ flex:1,background:`${d.c}10`,border:`1px solid ${d.c}22`,borderRadius:8,padding:"9px 10px",textAlign:"center" }}>
                    <div style={{ fontFamily:"var(--font-display)",fontSize:16,fontWeight:600,color:d.c }}>{d.n.toLocaleString("fr-FR")}</div>
                    <div style={{ fontSize:9,color:"var(--mut)",marginTop:2 }}>{d.l}</div>
                  </div>
                ))}
              </div>
              <ResponsiveContainer width="100%" height={80}>
                <BarChart data={TRUST_DIST} barSize={28}>
                  <XAxis dataKey="l" tick={{fill:"var(--mut)",fontSize:10}} axisLine={false} tickLine={false}/>
                  <YAxis hide/>
                  <Tooltip contentStyle={{background:"var(--el)",border:"1px solid var(--bor)",borderRadius:8}} cursor={false}/>
                  <Bar dataKey="n" radius={[4,4,0,0]}>{TRUST_DIST.map((d,i)=><Cell key={i} fill={d.c}/>)}</Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div style={{ background:"var(--card)",border:"1px solid var(--bor)",borderRadius:12,padding:22 }}>
              <div style={{ fontSize:13,fontWeight:600,marginBottom:12 }}>Types de biens</div>
              <div style={{ display:"flex",alignItems:"center",gap:12 }}>
                <PieChart width={100} height={100}>
                  <Pie data={PROP_DIST} dataKey="v" cx={50} cy={50} innerRadius={30} outerRadius={46} paddingAngle={2}>
                    {PROP_DIST.map((d,i)=><Cell key={i} fill={d.c}/>)}
                  </Pie>
                </PieChart>
                <div style={{ flex:1,display:"flex",flexDirection:"column",gap:5 }}>
                  {PROP_DIST.map(d=>(
                    <div key={d.name} style={{ display:"flex",alignItems:"center",gap:5 }}>
                      <div style={{ width:6,height:6,borderRadius:2,background:d.c,flexShrink:0 }}/>
                      <span style={{ fontSize:10,color:"var(--mut)",flex:1 }}>{d.name}</span>
                      <span style={{ fontSize:10,fontFamily:"var(--font-display)",fontWeight:600 }}>{d.v}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Alertes BO2 */}
          {alerts.length>0&&(
            <div style={{ background:"var(--card)",border:"1px solid var(--bor)",borderRadius:12,padding:20 }}>
              <div style={{ display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:12 }}>
                <span style={{ fontSize:13,fontWeight:600 }}>Alertes territoriales (BO2)</span>
                <a href="/territoire" style={{ fontSize:11,color:"var(--gold)",textDecoration:"none" }}>Voir tout →</a>
              </div>
              {alerts.map((a:any,i:number)=>(
                <div key={i} style={{ display:"flex",alignItems:"center",gap:8,padding:"7px 0",borderBottom:i<alerts.length-1?"1px solid var(--bor)":"none" }}>
                  <span style={{ fontSize:14 }}>{ICONS[a.alert_type]||"📌"}</span>
                  <span style={{ fontSize:12,fontWeight:500,flex:1 }}>{a.zone}</span>
                  <span style={{ fontSize:10,padding:"2px 7px",borderRadius:999,background:"rgba(82,200,150,.12)",color:"#52C896",border:"1px solid rgba(82,200,150,.25)" }}>
                    {a.price_growth?`${a.price_growth>0?"+":""}${(a.price_growth*100).toFixed(1)}% prix`:a.volume_growth?`+${(a.volume_growth*100).toFixed(1)}% vol`:"alerte"}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Analyses récentes */}
          <div style={{ background:"var(--card)",border:"1px solid var(--bor)",borderRadius:12,padding:22 }}>
            <div style={{ fontSize:13,fontWeight:600,marginBottom:14 }}>Analyses récentes</div>
            <div style={{ overflowX:"auto" }}>
              <table style={{ width:"100%",borderCollapse:"collapse",fontSize:12 }}>
                <thead>
                  <tr>{["Annonce","Ville","Type","Trust","Risque légal"].map(h=>(
                    <th key={h} style={{ padding:"8px 12px",textAlign:"left",fontSize:10,color:"var(--mut)",textTransform:"uppercase",letterSpacing:".05em",borderBottom:"1px solid var(--bor)",background:"var(--el)" }}>{h}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {stats.recent.map((a:any)=>(
                    <tr key={a.id} style={{ borderBottom:"1px solid rgba(255,255,255,.03)" }}>
                      <td style={{ padding:"10px 12px",whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis",maxWidth:180 }}>{a.title}</td>
                      <td style={{ padding:"10px 12px",color:"var(--mut)" }}>
                        <span style={{ display:"flex",alignItems:"center",gap:3 }}><MapPin size={10}/>{a.city}</span>
                      </td>
                      <td style={{ padding:"10px 12px",color:"var(--mut)",textTransform:"capitalize" }}>{a.type.replace("_"," ")}</td>
                      <td style={{ padding:"10px 12px" }}>
                        <div style={{ display:"flex",alignItems:"center",gap:6 }}>
                          <div style={{ width:36,height:3,background:"var(--el)",borderRadius:2,overflow:"hidden" }}>
                            <div style={{ height:"100%",width:`${a.trust*100}%`,background:TC(a.trust),borderRadius:2 }}/>
                          </div>
                          <span style={{ fontFamily:"var(--font-display)",fontSize:12,fontWeight:600 }}>{a.trust.toFixed(2)}</span>
                        </div>
                      </td>
                      <td style={{ padding:"10px 12px" }}>
                        <span style={{ fontSize:11,padding:"2px 8px",borderRadius:999,background:`${LLC[a.legal_level]||"#888"}14`,color:LLC[a.legal_level]||"#888",border:`1px solid ${LLC[a.legal_level]||"#888"}28` }}>
                          {a.legal_level}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Sidebar liens rapides */}
        <div style={{ background:"var(--card)",border:"1px solid var(--bor)",borderRadius:12,padding:22,position:"sticky",top:72 }}>
          <div style={{ fontSize:13,fontWeight:600,marginBottom:14,color:"var(--gold)" }}>Liens rapides</div>
          {[
            {href:"/opportunites",emoji:"💰",label:"Baisses de prix",    sub:"Biens négociables aujourd'hui"},
            {href:"/opportunites",emoji:"🏢",label:"Rendement locatif", sub:"Meilleures villes à investir"},
            {href:"/territoire",  emoji:"🚀",label:"Zones émergentes",  sub:"Alertes territoriales actives"},
            {href:"/recherche",   emoji:"🔍",label:"Recherche avancée", sub:"Filtres trust, budget, ville"},
            {href:"/carte",       emoji:"🗺️",label:"Carte interactive",  sub:"Heatmap + micro-marchés"},
          ].map(l=>(
            <a key={l.label} href={l.href} style={{ display:"flex",alignItems:"center",gap:10,padding:"10px 0",borderBottom:"1px solid var(--bor)",textDecoration:"none" }}>
              <span style={{ fontSize:18,flexShrink:0 }}>{l.emoji}</span>
              <div style={{ flex:1 }}>
                <div style={{ fontSize:12,fontWeight:500,color:"var(--txt)" }}>{l.label}</div>
                <div style={{ fontSize:10,color:"var(--mut)" }}>{l.sub}</div>
              </div>
              <span style={{ fontSize:12,color:"var(--gold)" }}>→</span>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
