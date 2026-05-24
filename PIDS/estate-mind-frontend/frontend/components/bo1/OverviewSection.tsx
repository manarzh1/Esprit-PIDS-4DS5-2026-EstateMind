"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from "recharts";
import {
  Database, Activity, ShieldCheck, AlertTriangle,
  MapPin, Sparkles, RefreshCw, TrendingUp, TrendingDown
} from "lucide-react";

// ── Demo data ─────────────────────────────────────────────────────────────────
const FALLBACK = {
  total_raw:14927, total_clean:8412, avg_trust:0.673,
  suspect_count:1303, high_legal:412,
  recent:[
    {id:1,title:"Villa S+4 Hammamet Nord",  city:"Hammamet",type:"villa",       trust:.84,legal:.15,trust_level:"Reliable",legal_level:"Low"},
    {id:2,title:"Land 800m² Nabeul",         city:"Nabeul",  type:"land",        trust:.31,legal:.72,trust_level:"Suspect", legal_level:"High"},
    {id:3,title:"Apartment S+2 La Marsa",    city:"La Marsa",type:"apartment",   trust:.71,legal:.28,trust_level:"Moderate",legal_level:"Medium"},
    {id:4,title:"Studio Downtown Tunis",     city:"Tunis",   type:"studio",      trust:.89,legal:.09,trust_level:"Reliable",legal_level:"Low"},
    {id:5,title:"Commercial space Sfax",     city:"Sfax",    type:"commercial",  trust:.55,legal:.43,trust_level:"Moderate",legal_level:"Medium"},
  ],
};
const PREV       = { total_clean:8100, avg_trust:0.648, suspect_count:1420 };
const TRUST_DIST = [
  {l:"Reliable",n:4821,c:"#238765"},
  {l:"Moderate",n:2288,c:"#bf7618"},
  {l:"Suspect", n:1303,c:"#cc3b25"},
];
const PROP_DIST = [
  {name:"Apartment",v:38,c:"#2f9c7e"},
  {name:"Villa",    v:24,c:"#238765"},
  {name:"Land",     v:18,c:"#bf7618"},
  {name:"House",    v:12,c:"#4a6fa5"},
  {name:"Studio",   v:8, c:"#7b68c8"},
];
const DEMO_BO2 = [
  {zone:"Hammamet",alert_type:"emerging",  price_growth:0.152},
  {zone:"Nabeul",  alert_type:"price_surge",price_growth:0.122},
  {zone:"Mahdia",  alert_type:"volume_surge",volume_growth:0.312},
];
const INSIGHTS = [
  "3 active territorial alerts today. Hammamet continues rising (+15.2%) — 30-day opportunity window. 8,412 reliable listings. Average trust score slightly improving.",
  "Mahdia records +31% listing volume without price increase — zone to watch. Greater Tunis holds 42% of national volume. No drift detected.",
  "Sousse in moderate emerging zone. Pipeline running every 6h. Dataset quality: 82/100. Average trust 0.673 — real market, not perfect.",
];
const ICONS: Record<string,string> = {emerging:"🚀",price_surge:"📈",volume_surge:"📊",declining:"📉"};
const TC = (s:number) => s>=.75?"var(--ok)":s>=.5?"var(--warn)":"var(--bad)";
const LLC: Record<string,string> = {"Low":"#238765","Medium":"#bf7618","High":"#cc3b25"};

// ── Animated KPI ──────────────────────────────────────────────────────────────
function KpiCounter({ label,value,color,sub,prev,higherIsBetter=true,decimals=0,icon }: {
  label:string;value:number;color?:string;sub?:string;
  prev?:number;higherIsBetter?:boolean;decimals?:number;icon?:React.ReactNode;
}) {
  const [shown, setShown] = useState(0);
  const frame = useRef<number|null>(null);
  const start = useRef<number|null>(null);
  useEffect(()=>{
    start.current = null;
    const go = (ts:number)=>{
      if(!start.current) start.current = ts;
      const p = Math.min((ts-start.current)/1200,1);
      const e = 1-Math.pow(1-p,3);
      setShown(e*value);
      if(p<1) frame.current = requestAnimationFrame(go);
    };
    frame.current = requestAnimationFrame(go);
    return ()=>{ if(frame.current) cancelAnimationFrame(frame.current); };
  },[value]);

  const hasDelta = prev!==undefined;
  const delta = hasDelta ? ((value-prev!)/Math.abs(prev!)*100) : 0;
  const good = higherIsBetter ? delta>0 : delta<0;
  const dc = good ? "var(--ok)" : "var(--bad)";

  return (
    <div className="kpi-card">
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
        <div style={{flex:1}}>
          <div className="kpi-label">{label}</div>
          <div className="kpi-value" style={{color: color||"var(--navy)"}}>
            {decimals>0 ? shown.toFixed(decimals) : Math.round(shown).toLocaleString("en-US")}
          </div>
          {hasDelta && (
            <div style={{display:"flex",alignItems:"center",gap:3,fontSize:11,color:dc,marginTop:4}}>
              {delta>0?<TrendingUp size={10}/>:<TrendingDown size={10}/>}
              <span style={{fontWeight:700}}>{delta>0?"+":""}{delta.toFixed(1)}%</span>
              <span style={{color:"var(--mut)",fontSize:9}}>vs previous</span>
            </div>
          )}
          {sub && <div className="kpi-sub">{sub}</div>}
        </div>
        {icon && (
          <div style={{width:36,height:36,borderRadius:10,background:`rgba(47,156,126,.12)`,display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function OverviewSection() {
  const [stats,      setStats]      = useState<any>(FALLBACK);
  const [alerts,     setAlerts]     = useState<any[]>(DEMO_BO2);
  const [insight,    setInsight]    = useState(INSIGHTS[0]);
  const [loading,    setLoading]    = useState(false);
  const [insLoading, setInsLoading] = useState(false);
  const [lastAt,     setLastAt]     = useState("");
  const idxRef   = useRef(0);
  const interval = useRef<any>(null);

  const loadInsight = useCallback(async (silent=false)=>{
    if(!silent) setInsLoading(true);
    try {
      const r = await fetch("/api/insight");
      if(r.ok){ const d=await r.json(); setInsight(d.insight||INSIGHTS[idxRef.current%INSIGHTS.length]); }
      else { setInsight(INSIGHTS[idxRef.current%INSIGHTS.length]); idxRef.current++; }
    } catch { setInsight(INSIGHTS[idxRef.current%INSIGHTS.length]); idxRef.current++; }
    if(!silent) setInsLoading(false);
  },[]);

  const refresh = useCallback(async (silent=false)=>{
    if(!silent) setLoading(true);
    try {
      const r = await fetch("/api/dashboard");
      if(r.ok) setStats(await r.json());
    } catch {}
    try {
      const r2 = await fetch("/api/territorial/alerts?lookback_recent=45");
      if(r2.ok){ const d=await r2.json(); if(d?.alerts?.length) setAlerts(d.alerts.slice(0,3)); else setAlerts(DEMO_BO2); }
      else setAlerts(DEMO_BO2);
    } catch { setAlerts(DEMO_BO2); }
    setLastAt(new Date().toLocaleTimeString("en-US",{hour:"2-digit",minute:"2-digit",second:"2-digit"}));
    if(!silent) setLoading(false);
  },[]);

  useEffect(()=>{
    loadInsight(); refresh();
    interval.current = setInterval(()=>refresh(true),60000);
    return ()=>clearInterval(interval.current);
  },[]);

  return (
    <div style={{display:"flex",flexDirection:"column",gap:20}}>
      {/* Header */}
      <div className="dash-topbar">
        <div>
          <h1>Overview</h1>
          <p>Tunisian real estate market — Estate Mind PropTech</p>
        </div>
        <div className="topbar-actions">
          {lastAt && <span style={{fontSize:10,color:"var(--mut)"}}>Updated {lastAt}</span>}
          <button className="btn" onClick={()=>refresh()} disabled={loading}>
            <RefreshCw size={11} style={{animation:loading?"spin 1s linear infinite":"none"}}/>
            {loading?"...":"Refresh"}
          </button>
          <div style={{display:"flex",alignItems:"center",gap:5}}>
            <div style={{width:6,height:6,borderRadius:"50%",background:"var(--ok)",animation:"pulse 2s ease-in-out infinite"}}/>
            <span style={{fontSize:10,color:"var(--mut)"}}>Auto 60s</span>
          </div>
        </div>
      </div>

      {/* Insight */}
      <div className="insight-banner">
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8}}>
          <div style={{display:"flex",alignItems:"center",gap:7}}>
            <div style={{width:22,height:22,borderRadius:6,background:"rgba(47,156,126,.15)",display:"flex",alignItems:"center",justifyContent:"center"}}>
              <Sparkles size={11} color="var(--green)"/>
            </div>
            <span style={{fontSize:12,fontWeight:700,color:"var(--green)"}}>Daily Insight</span>
          </div>
          <button className="btn-ghost btn" onClick={()=>loadInsight()}>
            <RefreshCw size={10} style={{animation:insLoading?"spin 1s linear infinite":"none"}}/>
          </button>
        </div>
        {insLoading
          ? <span style={{fontSize:12,color:"var(--mut)"}}>Generating...</span>
          : <p style={{fontSize:13,color:"var(--txt)",lineHeight:1.7}}>{insight}</p>
        }
      </div>

      {/* KPIs */}
      <div className="kpi-grid">
        <KpiCounter label="Raw listings"    value={stats.total_raw}    sub="annonces_combined.csv"    icon={<Database size={15} color="#4a6fa5"/>} />
        <KpiCounter label="After cleaning"  value={stats.total_clean}  color="var(--ok)" sub={`${Math.round(stats.total_clean/Math.max(stats.total_raw,1)*100)}% kept`} prev={PREV.total_clean}  higherIsBetter icon={<Activity size={15} color="var(--ok)"/>} />
        <KpiCounter label="Avg trust score" value={stats.avg_trust}    color="#4a6fa5" sub="global reliability" prev={PREV.avg_trust} higherIsBetter decimals={3} icon={<ShieldCheck size={15} color="#4a6fa5"/>} />
        <KpiCounter label="Suspect listings" value={stats.suspect_count} color="var(--bad)" sub="trust_score < 0.50" prev={PREV.suspect_count} higherIsBetter={false} icon={<AlertTriangle size={15} color="var(--bad)"/>} />
      </div>

      {/* Main grid */}
      <div style={{display:"grid",gridTemplateColumns:"1fr 340px",gap:16,alignItems:"start"}}>
        <div style={{display:"flex",flexDirection:"column",gap:14}}>
          {/* Charts */}
          <div className="charts-grid">
            {/* Trust distribution */}
            <div className="panel">
              <div className="panel-head"><h3>Trust Score Distribution</h3></div>
              <div style={{display:"flex",gap:8,marginBottom:12}}>
                {TRUST_DIST.map(d=>(
                  <div key={d.l} style={{flex:1,background:`${d.c}12`,border:`1px solid ${d.c}28`,borderRadius:10,padding:"8px 10px",textAlign:"center"}}>
                    <div style={{fontFamily:"var(--font-display)",fontSize:18,fontWeight:700,color:d.c}}>{d.n.toLocaleString("en-US")}</div>
                    <div style={{fontSize:10,color:"var(--mut)",marginTop:2}}>{d.l}</div>
                  </div>
                ))}
              </div>
              <ResponsiveContainer width="100%" height={80}>
                <BarChart data={TRUST_DIST} barSize={32}>
                  <XAxis dataKey="l" tick={{fill:"var(--mut)",fontSize:10}} axisLine={false} tickLine={false}/>
                  <YAxis hide/>
                  <Tooltip contentStyle={{background:"white",border:"1px solid var(--line)",borderRadius:10,fontSize:12}} cursor={false}/>
                  <Bar dataKey="n" radius={[4,4,0,0]}>{TRUST_DIST.map((d,i)=><Cell key={i} fill={d.c}/>)}</Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            {/* Property types */}
            <div className="panel">
              <div className="panel-head"><h3>Property Types</h3></div>
              <div style={{display:"flex",alignItems:"center",gap:14}}>
                <PieChart width={100} height={100}>
                  <Pie data={PROP_DIST} dataKey="v" cx={50} cy={50} innerRadius={30} outerRadius={46} paddingAngle={2}>
                    {PROP_DIST.map((d,i)=><Cell key={i} fill={d.c}/>)}
                  </Pie>
                </PieChart>
                <div style={{flex:1,display:"flex",flexDirection:"column",gap:4}}>
                  {PROP_DIST.map(d=>(
                    <div key={d.name} style={{display:"flex",alignItems:"center",gap:6}}>
                      <div style={{width:7,height:7,borderRadius:2,background:d.c,flexShrink:0}}/>
                      <span style={{fontSize:11,color:"var(--mut)",flex:1}}>{d.name}</span>
                      <span style={{fontSize:11,fontWeight:700}}>{d.v}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Territorial alerts */}
          {alerts.length>0 && (
            <div className="panel">
              <div className="panel-head">
                <h3>Territorial Alerts <span style={{fontSize:11,background:"rgba(47,156,126,.12)",color:"var(--green)",padding:"2px 7px",borderRadius:999,fontWeight:700}}>BO2</span></h3>
                <a href="/bo2" style={{fontSize:12,color:"var(--green)",fontWeight:700}}>View all →</a>
              </div>
              {alerts.map((a:any,i:number)=>(
                <div key={i} style={{display:"flex",alignItems:"center",gap:10,padding:"9px 0",borderBottom:i<alerts.length-1?"1px solid var(--line)":"none"}}>
                  <span style={{fontSize:16}}>{ICONS[a.alert_type]||"📌"}</span>
                  <span style={{fontSize:13,fontWeight:600,flex:1}}>{a.zone}</span>
                  <span style={{fontSize:11,padding:"3px 9px",borderRadius:999,background:"rgba(35,135,101,.1)",color:"var(--ok)",border:"1px solid rgba(35,135,101,.25)",fontWeight:700}}>
                    {a.price_growth?`${a.price_growth>0?"+":""}${(a.price_growth*100).toFixed(1)}% price`:
                     a.volume_growth?`+${(a.volume_growth*100).toFixed(1)}% vol`:"alert"}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Recent analyses */}
          <div className="panel">
            <div className="panel-head"><h3>Recent Analyses</h3></div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>{["Listing","City","Type","Trust","Legal Risk"].map(h=><th key={h}>{h}</th>)}</tr>
                </thead>
                <tbody>
                  {stats.recent.map((a:any)=>(
                    <tr key={a.id}>
                      <td style={{whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis",maxWidth:180,fontWeight:500}}>{a.title}</td>
                      <td style={{color:"var(--mut)"}}>
                        <span style={{display:"flex",alignItems:"center",gap:3}}><MapPin size={10}/>{a.city}</span>
                      </td>
                      <td style={{color:"var(--mut)",textTransform:"capitalize"}}>{(a.type||"").replace("_"," ")}</td>
                      <td>
                        <div className="trust-bar">
                          <div className="trust-bar-track">
                            <div className="trust-bar-fill" style={{width:`${a.trust*100}%`,background:TC(a.trust)}}/>
                          </div>
                          <span style={{fontFamily:"var(--font-display)",fontSize:12,fontWeight:700,color:TC(a.trust)}}>{a.trust.toFixed(2)}</span>
                        </div>
                      </td>
                      <td>
                        <span className={`risk ${a.legal_level==="High"?"high":a.legal_level==="Medium"?"mid":"low"}`}>
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

        {/* Quick links sidebar */}
        <div className="panel" style={{position:"sticky",top:20}}>
          <h3 style={{fontSize:14,fontWeight:700,marginBottom:16,color:"var(--green)"}}>Quick Links</h3>
          {[
            {href:"/bo1?tab=opportunities",icon:"💰",label:"Price Drops",    sub:"Negotiable listings today"},
            {href:"/bo2?tab=territory",    icon:"🚀",label:"Emerging Zones", sub:"Active territorial alerts"},
            {href:"/bo1?tab=search",       icon:"🔍",label:"Advanced Search", sub:"Trust, budget, city filters"},
            {href:"/bo2?tab=map",          icon:"🗺",label:"Interactive Map",  sub:"Heatmap + micro-markets"},
            {href:"/bo3",                  icon:"📊",label:"Price Estimator",  sub:"AI-powered valuation"},
          ].map(l=>(
            <a key={l.label} href={l.href} style={{display:"flex",alignItems:"center",gap:10,padding:"10px 0",borderBottom:"1px solid var(--line)",textDecoration:"none",transition:"all .15s"}}
               onMouseEnter={e=>(e.currentTarget.style.paddingLeft="4px")}
               onMouseLeave={e=>(e.currentTarget.style.paddingLeft="0")}>
              <span style={{fontSize:18,flexShrink:0}}>{l.icon}</span>
              <div style={{flex:1}}>
                <div style={{fontSize:13,fontWeight:600,color:"var(--txt)"}}>{l.label}</div>
                <div style={{fontSize:10,color:"var(--mut)"}}>{l.sub}</div>
              </div>
              <span style={{fontSize:13,color:"var(--green)",fontWeight:700}}>→</span>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
