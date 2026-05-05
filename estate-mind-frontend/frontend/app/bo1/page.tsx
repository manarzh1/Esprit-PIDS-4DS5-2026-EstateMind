"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line
} from "recharts";
import { RefreshCw, Sparkles, TrendingDown, TrendingUp, Minus, Star, Trash2,
         Bell, BellOff, ChevronDown, ChevronUp, Search, SlidersHorizontal, X,
         Clock, MapPin, ExternalLink } from "lucide-react";
import { ReferenceLine } from "recharts";

/* ═══════════════════════════════════════════════════════════════════
   SHARED HELPERS & TYPES
   ═══════════════════════════════════════════════════════════════════ */
const TC  = (s:number) => s>=.75?"#238765":s>=.5?"#bf7618":"#cc3b25";
const LC  = (s:number) => s<.3?"#238765":s<.6?"#bf7618":"#cc3b25";
const LCL = (s:string) => ({Low:"low",Medium:"mid",High:"high"}[s]||"mid");

/* ═══════════════════════════════════════════════════════════════════
   TAB 1 — OVERVIEW
   ═══════════════════════════════════════════════════════════════════ */
const OVERVIEW_FALLBACK = {
  total_raw:14927, total_clean:8412, avg_trust:0.673, suspect_count:1303,
  recent:[
    {id:1,title:"Villa S+4 Hammamet Nord",  city:"Hammamet",type:"villa",      trust:.84,legal_level:"Low"},
    {id:2,title:"Land 800m² Nabeul",         city:"Nabeul",  type:"land",       trust:.31,legal_level:"High"},
    {id:3,title:"Apartment S+2 La Marsa",    city:"La Marsa",type:"apartment",  trust:.71,legal_level:"Medium"},
    {id:4,title:"Studio Downtown Tunis",     city:"Tunis",   type:"studio",     trust:.89,legal_level:"Low"},
    {id:5,title:"Commercial Sfax",           city:"Sfax",    type:"commercial", trust:.55,legal_level:"Medium"},
  ],
};
const TRUST_DIST = [{l:"Reliable",n:4821,c:"#238765"},{l:"Moderate",n:2288,c:"#bf7618"},{l:"Suspect",n:1303,c:"#cc3b25"}];
const PROP_DIST  = [{name:"Apartment",v:38,c:"#2f9c7e"},{name:"Villa",v:24,c:"#238765"},{name:"Land",v:18,c:"#bf7618"},{name:"House",v:12,c:"#4a6fa5"},{name:"Studio",v:8,c:"#7b68c8"}];
const DEMO_BO2   = [{zone:"Hammamet",alert_type:"emerging",price_growth:0.152},{zone:"Nabeul",alert_type:"price_surge",price_growth:0.122},{zone:"Mahdia",alert_type:"volume_surge",volume_growth:0.312}];
const INSIGHTS   = ["3 active territorial alerts today. Hammamet rising (+15.2%) — 30-day window. 8,412 reliable listings. Trust score improving.","Mahdia +31% volume without price increase. Greater Tunis = 42% of national volume."];
const ICONS: Record<string,string> = {emerging:"🚀",price_surge:"📈",volume_surge:"📊",declining:"📉"};

function AnimNum({v,d=0}:{v:number;d?:number}) {
  const [n,sn]=useState(0);const f=useRef<any>(null);const s=useRef<any>(null);
  useEffect(()=>{s.current=null;const go=(ts:number)=>{if(!s.current)s.current=ts;const p=Math.min((ts-s.current)/1200,1);sn((1-Math.pow(1-p,3))*v);if(p<1)f.current=requestAnimationFrame(go);};f.current=requestAnimationFrame(go);return()=>{if(f.current)cancelAnimationFrame(f.current);};},[v]);
  return <>{d>0?n.toFixed(d):Math.round(n).toLocaleString("en-US")}</>;
}

function OverviewTab() {
  const [stats,setStats]=useState<any>(OVERVIEW_FALLBACK);
  const [alerts,setAlerts]=useState<any[]>(DEMO_BO2);
  const [insight,setInsight]=useState(INSIGHTS[0]);
  const [loading,setLoading]=useState(false);
  const [insLoad,setInsLoad]=useState(false);
  const [lastAt,setLastAt]=useState("");
  const idx=useRef(0);

  const refresh=useCallback(async(silent=false)=>{
    if(!silent)setLoading(true);
    try{const r=await fetch("/api/dashboard");if(r.ok)setStats(await r.json());}catch{}
    try{const r=await fetch("/api/territorial/alerts?lookback_recent=45");if(r.ok){const d=await r.json();if(d?.alerts?.length)setAlerts(d.alerts.slice(0,3));}}catch{}
    setLastAt(new Date().toLocaleTimeString("en-US",{hour:"2-digit",minute:"2-digit",second:"2-digit"}));
    if(!silent)setLoading(false);
  },[]);
  const loadInsight=useCallback(async()=>{
    setInsLoad(true);
    try{const r=await fetch("/api/insight");if(r.ok){const d=await r.json();setInsight(d.insight||INSIGHTS[idx.current++%INSIGHTS.length]);}else setInsight(INSIGHTS[idx.current++%INSIGHTS.length]);}
    catch{setInsight(INSIGHTS[idx.current++%INSIGHTS.length]);}
    setInsLoad(false);
  },[]);

  useEffect(()=>{loadInsight();refresh();const t=setInterval(()=>refresh(true),60000);return()=>clearInterval(t);},[]);

  return (
    <div style={{display:"flex",flexDirection:"column",gap:20}}>
      {/* Sub-header */}
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",flexWrap:"wrap",gap:12}}>
        <div>
          <h2 style={{fontFamily:"Georgia,serif",fontSize:22,fontWeight:600,marginBottom:4}}>Overview</h2>
          <p style={{fontSize:13,color:"var(--muted)"}}>Tunisian real estate market — Estate Mind PropTech</p>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          {lastAt&&<span style={{fontSize:10,color:"var(--muted)"}}>Updated {lastAt}</span>}
          <button onClick={()=>refresh()} disabled={loading} className="btn" style={{padding:"8px 14px",fontSize:12}}>
            <RefreshCw size={11} style={{animation:loading?"spin 1s linear infinite":"none",marginRight:5}}/>{loading?"...":"Refresh"}
          </button>
          <div style={{display:"flex",alignItems:"center",gap:5}}>
            <div style={{width:6,height:6,borderRadius:"50%",background:"var(--green)"}}/>
            <span style={{fontSize:10,color:"var(--muted)"}}>Auto 60s</span>
          </div>
        </div>
      </div>

      {/* Insight banner */}
      <div style={{background:"linear-gradient(135deg,rgba(47,156,126,.08),rgba(71,213,177,.04))",border:"1px solid rgba(47,156,126,.22)",borderRadius:18,padding:"14px 18px"}}>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8}}>
          <div style={{display:"flex",alignItems:"center",gap:7}}>
            <Sparkles size={14} color="var(--green)"/>
            <span style={{fontSize:12,fontWeight:700,color:"var(--green)"}}>Daily Insight</span>
          </div>
          <button onClick={loadInsight} style={{background:"none",border:"none",cursor:"pointer",color:"var(--muted)",padding:2}}>
            <RefreshCw size={10} style={{animation:insLoad?"spin 1s linear infinite":"none"}}/>
          </button>
        </div>
        {insLoad?<span style={{fontSize:12,color:"var(--muted)"}}>Generating...</span>
          :<p style={{fontSize:13,color:"var(--text)",lineHeight:1.7,margin:0}}>{insight}</p>}
      </div>

      {/* ── KPI Cards — exact .kpi-card + .dash-grid classes ── */}
      <section className="dash-grid">
        <article className="kpi-card">
          <span>Raw listings</span>
          <strong><AnimNum v={stats.total_raw}/></strong>
          <small>annonces_combined.csv</small>
        </article>
        <article className="kpi-card">
          <span>After cleaning</span>
          <strong style={{color:"var(--green)"}}><AnimNum v={stats.total_clean}/></strong>
          <small>{Math.round(stats.total_clean/Math.max(stats.total_raw,1)*100)}% kept</small>
        </article>
        <article className="kpi-card">
          <span>Avg trust score</span>
          <strong style={{color:"#4a6fa5"}}><AnimNum v={stats.avg_trust} d={3}/></strong>
          <small>global reliability</small>
        </article>
        <article className="kpi-card">
          <span>Suspect listings</span>
          <strong style={{color:"#cc3b25"}}><AnimNum v={stats.suspect_count}/></strong>
          <small>trust_score &lt; 0.50</small>
        </article>
      </section>

      {/* ── Panels row — charts + table ── */}
      <section className="dash-grid" style={{gridTemplateColumns:"1fr 1fr"}}>
        <article className="panel" style={{minHeight:"auto"}}>
          <div className="panel-head"><h3>Trust Score Distribution</h3></div>
          <div style={{display:"flex",gap:8,marginBottom:12}}>
            {TRUST_DIST.map(d=>(
              <div key={d.l} style={{flex:1,background:`${d.c}12`,border:`1px solid ${d.c}28`,borderRadius:10,padding:"8px 10px",textAlign:"center"}}>
                <div style={{fontFamily:"Georgia,serif",fontSize:18,fontWeight:700,color:d.c}}>{d.n.toLocaleString("en-US")}</div>
                <div style={{fontSize:10,color:"var(--muted)",marginTop:2}}>{d.l}</div>
              </div>
            ))}
          </div>
          <ResponsiveContainer width="100%" height={80}>
            <BarChart data={TRUST_DIST} barSize={32}>
              <XAxis dataKey="l" tick={{fill:"var(--muted)",fontSize:10}} axisLine={false} tickLine={false}/>
              <YAxis hide/>
              <Tooltip contentStyle={{background:"white",border:"1px solid var(--line)",borderRadius:10,fontSize:11}} cursor={false}/>
              <Bar dataKey="n" radius={[4,4,0,0]}>{TRUST_DIST.map((d,i)=><Cell key={i} fill={d.c}/>)}</Bar>
            </BarChart>
          </ResponsiveContainer>
        </article>

        <article className="panel" style={{minHeight:"auto"}}>
          <div className="panel-head"><h3>Property Types</h3></div>
          <div style={{display:"flex",alignItems:"center",gap:14}}>
            <PieChart width={100} height={100}>
              <Pie data={PROP_DIST} dataKey="v" cx={50} cy={50} innerRadius={30} outerRadius={46} paddingAngle={2}>
                {PROP_DIST.map((d,i)=><Cell key={i} fill={d.c}/>)}
              </Pie>
            </PieChart>
            <div style={{flex:1,display:"flex",flexDirection:"column",gap:5}}>
              {PROP_DIST.map(d=>(
                <div key={d.name} style={{display:"flex",alignItems:"center",gap:6}}>
                  <div style={{width:7,height:7,borderRadius:2,background:d.c,flexShrink:0}}/>
                  <span style={{fontSize:11,color:"var(--muted)",flex:1}}>{d.name}</span>
                  <span style={{fontSize:11,fontWeight:700}}>{d.v}%</span>
                </div>
              ))}
            </div>
          </div>
        </article>
      </section>

      {/* Territorial alerts + Recent analyses */}
      <section className="dash-grid" style={{gridTemplateColumns:"1fr 1fr"}}>
        {alerts.length>0&&(
          <article className="panel table-panel" style={{minHeight:"auto"}}>
            <div className="panel-head">
              <h3>Territorial Alerts <span className="eyebrow" style={{fontSize:10,padding:"3px 8px",marginLeft:6}}>BO2</span></h3>
              <a href="/bo2?tab=territory" style={{fontSize:12,color:"#2f9c7e",fontWeight:700,textDecoration:"none"}}>View all →</a>
            </div>
            {alerts.map((a:any,i:number)=>(
              <div key={i} style={{display:"flex",alignItems:"center",gap:10,padding:"9px 0",borderBottom:i<alerts.length-1?"1px solid var(--line)":"none"}}>
                <span style={{fontSize:16}}>{ICONS[a.alert_type]||"📌"}</span>
                <span style={{fontSize:13,fontWeight:600,flex:1}}>{a.zone}</span>
                <span className="risk low">
                  {a.price_growth?`${a.price_growth>0?"+":""}${(a.price_growth*100).toFixed(1)}% price`:a.volume_growth?`+${(a.volume_growth*100).toFixed(1)}% vol`:"alert"}
                </span>
              </div>
            ))}
          </article>
        )}

      </section>

      {/* Recent Analyses + Quick Links side by side */}
      <div style={{display:"grid",gridTemplateColumns:"1fr 320px",gap:18,alignItems:"start"}}>
        <article className="panel" style={{minHeight:"auto"}}>
          <div className="panel-head"><h3>Recent Analyses</h3><a href="/bo1?tab=search" style={{fontSize:12,color:"#2f9c7e",fontWeight:700,textDecoration:"none",padding:"8px 13px",border:"1px solid #e6eaf0",borderRadius:12,background:"white"}}>View all</a></div>
          <table>
            <thead><tr><th>Listing</th><th>City</th><th>Trust</th><th>Legal Risk</th></tr></thead>
            <tbody>
              {stats.recent.map((a:any)=>(
                <tr key={a.id}>
                  <td style={{maxWidth:200,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",fontWeight:500}}>{a.title}</td>
                  <td style={{color:"var(--muted)"}}>{a.city}</td>
                  <td>
                    <div style={{display:"flex",alignItems:"center",gap:6}}>
                      <div style={{width:36,height:4,background:"var(--line)",borderRadius:2,overflow:"hidden"}}>
                        <div style={{height:"100%",width:`${a.trust*100}%`,background:TC(a.trust),borderRadius:2}}/>
                      </div>
                      <span style={{fontWeight:700,color:TC(a.trust)}}>{a.trust.toFixed(2)}</span>
                    </div>
                  </td>
                  <td><span className={`risk ${LCL(a.legal_level)}`}>{a.legal_level}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>

        <article className="panel" style={{minHeight:"auto",position:"sticky",top:20}}>
          <div className="panel-head"><h3 style={{color:"var(--green)"}}>Quick Links</h3></div>
          {[
            {href:"/bo1?tab=search",       icon:"🔍",label:"Advanced Search",  sub:"Trust, budget, city filters"},
            {href:"/bo1?tab=opportunities",icon:"💰",label:"Price Drops",      sub:"Negotiable listings today"},
            {href:"/bo2?tab=territory",    icon:"🚀",label:"Emerging Zones",   sub:"Active territorial alerts"},
            {href:"/bo2?tab=map",          icon:"🗺",label:"Interactive Map",  sub:"Heatmap + micro-markets"},
            {href:"/bo3",                  icon:"📊",label:"Price Estimator",  sub:"AI-powered valuation"},
          ].map(l=>(
            <a key={l.label} href={l.href} style={{display:"flex",alignItems:"center",gap:10,padding:"10px 0",borderBottom:"1px solid var(--line)"}}>
              <span style={{fontSize:18,flexShrink:0}}>{l.icon}</span>
              <div style={{flex:1}}>
                <div style={{fontSize:13,fontWeight:600,color:"var(--text)"}}>{l.label}</div>
                <div style={{fontSize:10,color:"var(--muted)"}}>{l.sub}</div>
              </div>
              <span style={{fontSize:13,color:"var(--green)",fontWeight:700}}>→</span>
            </a>
          ))}
        </article>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   TAB 2 — SEARCH  (import from existing component)
   ═══════════════════════════════════════════════════════════════════ */
// Inline stub — full SearchSection is in components/bo1/SearchSection.tsx
import SearchSection        from "@/components/bo1/SearchSection";
import OpportunitiesSection from "@/components/bo1/OpportunitiesSection";
import PortfolioSection     from "@/components/bo1/PortfolioSection";

/* ═══════════════════════════════════════════════════════════════════
   BO1 PAGE
   ═══════════════════════════════════════════════════════════════════ */
type Tab = "overview"|"search"|"opportunities"|"portfolio";
const TABS:{id:Tab;label:string}[] = [
  {id:"overview",label:"Overview"},{id:"search",label:"Search"},
  {id:"opportunities",label:"Opportunities"},{id:"portfolio",label:"Portfolio"},
];

export default function BO1Page() {
  const [tab,setTab] = useState<Tab>("overview");
  const params = useSearchParams();
  useEffect(()=>{const t=params.get("tab") as Tab|null;if(t&&TABS.find(x=>x.id===t))setTab(t);},[params]);

  return (
    <>
      {/* ── Header — exact .dash-header structure from dashboard.html ── */}
      <header className="dash-header">
        <div>
          <span className="eyebrow">Smart Dashboard</span>
          <h1>BO1 — Market Reliability</h1>
        </div>
        <div className="header-actions">
          <div className="dash-search">
            <img src="/assets/icons/house.png" alt="" />
            <input placeholder="Search a listing, city, score..." readOnly />
          </div>
          <button className="icon-btn"><img src="/assets/icons/bell.png" alt="" /></button>
          <div className="profile">
            <img src="/assets/avatar-director.png" alt="Admin" />
            <span>Admin</span>
          </div>
        </div>
      </header>

      {/* ── Tabs — exact .dash-tabs from dashboard.css ── */}
      <section className="dash-tabs">
        {TABS.map(t=>(
          <button key={t.id} className={tab===t.id?"active":""} onClick={()=>setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </section>

      {/* ── Content ── */}
      <div className="animate-in">
        {tab==="overview"      && <OverviewTab/>}
        {tab==="search"        && <SearchSection/>}
        {tab==="opportunities" && <OpportunitiesSection/>}
        {tab==="portfolio"     && <PortfolioSection/>}
      </div>

      <footer className="dash-footer">Estate Mind © 2026 · AI Real Estate Intelligence</footer>
    </>
  );
}
