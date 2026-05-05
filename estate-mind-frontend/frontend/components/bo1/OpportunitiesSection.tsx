"use client";
import { useState, useEffect, useCallback } from "react";
import { DEMO_LISTINGS, DEMO_DROPS, DEMO_YIELD, type Listing } from "@/lib/demo-listings";
import { TrendingDown, TrendingUp, Clock, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LineChart, Line, ReferenceLine } from "recharts";
/* ── Derived demo data from shared listings ──────────────────── */
const DEMO_NEGO = DEMO_LISTINGS
  .filter(l => l.days_on_market > 60 && l.trust_score >= 0.5)
  .map(l => ({
    ...l,
    negociation_score: Math.min(0.95, 0.4 + l.days_on_market/400 + (1-l.trust_score)*0.3),
    seller_type: ["private","private","info_agency","active_reseller"][Math.floor(l.id%4)],
    estimated_reduction_pct: parseFloat((5 + l.days_on_market/30).toFixed(1)),
  }))
  .sort((a,b) => b.negociation_score - a.negociation_score);

const DEMO_WINDOW = {
  monthly_index:[
    {month:1, month_name:"January",  delta_vs_avg:-4.2,verdict:"favorable"},
    {month:2, month_name:"February", delta_vs_avg:-3.8,verdict:"favorable"},
    {month:3, month_name:"March",    delta_vs_avg:-1.5,verdict:"neutral"},
    {month:4, month_name:"April",    delta_vs_avg:1.2, verdict:"neutral"},
    {month:5, month_name:"May",      delta_vs_avg:3.5, verdict:"unfavorable"},
    {month:6, month_name:"June",     delta_vs_avg:5.1, verdict:"unfavorable"},
    {month:7, month_name:"July",     delta_vs_avg:6.8, verdict:"unfavorable"},
    {month:8, month_name:"August",   delta_vs_avg:4.2, verdict:"unfavorable"},
    {month:9, month_name:"September",delta_vs_avg:2.1, verdict:"neutral"},
    {month:10,month_name:"October",  delta_vs_avg:0.5, verdict:"neutral"},
    {month:11,month_name:"November", delta_vs_avg:-2.3,verdict:"favorable"},
    {month:12,month_name:"December", delta_vs_avg:-5.5,verdict:"favorable"},
  ],
  current_month:"April", current_verdict:"neutral", current_delta_pct:1.2,
  recommendation:"Neutral period (+1.2% vs average). Best months to buy: December, January, February.",
};


export default function OpportunitiesSection() {
  const [drops,setDrops]=useState<any>(DEMO_DROPS);
  const [yield_,setYield]=useState<any>({results:DEMO_YIELD,best_city:"Tunis",avg_yield:4.1});
  const [nego,setNego]=useState<any[]>(DEMO_NEGO);
  const [window_,setWindow]=useState<any>(DEMO_WINDOW);
  const [subTab,setSubTab]=useState<"drops"|"yield"|"nego"|"window">("drops");
  const [loading,setLoading]=useState(false);
  const [expandedDrops,setExpandedDrops]=useState<string[]>([]);

  const refresh = useCallback(async()=>{
    setLoading(true);
    try{const r=await fetch("/api/market/price-drops");if(r.ok)setDrops(await r.json());}catch{}
    try{const r=await fetch("/api/market/rental-yield");if(r.ok){const d=await r.json();setYield({results:d.results||DEMO_YIELD,best_city:d.best_city||'Tunis',avg_yield:d.avg_yield||4.1});}}catch{}
    try{const r=await fetch("/api/market/negotiable");if(r.ok){const d=await r.json();if(d.listings?.length)setNego(d.listings);}}catch{}
    try{const r=await fetch("/api/market/buying-window");if(r.ok)setWindow(await r.json());}catch{}
    setLoading(false);
  },[]);

  useEffect(()=>{refresh();},[]);

  const SUB_TABS = [
    {id:"drops" as const, label:"Price Drops",     count:drops.total},
    {id:"yield" as const, label:"Rental Yield",    count:yield_.results?.length||0},
    {id:"nego"  as const, label:"Negotiable",       count:nego.length},
    {id:"window"as const, label:"Buying Window",   count:null},
  ];

  return (
    <div style={{display:"flex",flexDirection:"column",gap:16}}>
      {/* Header */}
      <div className="dash-topbar">
        <div>
          <h1>Market Opportunities</h1>
          <p>5 tools unavailable anywhere else in Tunisia — buy at the right price, at the right time</p>
        </div>
        <button className="btn" onClick={refresh} disabled={loading}>
          <RefreshCw size={11} style={{animation:loading?"spin 1s linear infinite":"none"}}/>
          Refresh
        </button>
      </div>

      {/* KPIs */}
      <div className="dash-grid">
        <div className="kpi-card">
          <div className="kpi-label">Price drops detected</div>
          <div className="kpi-value" style={{color:"var(--ok)"}}>{drops.total}</div>
          <div className="kpi-sub">avg. {drops.avg_drop_pct?.toFixed(1)}%</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Best gross yield</div>
          <div className="kpi-value" style={{color:"var(--navy)"}}>{(DEMO_YIELD.reduce((s:any,r:any)=>s+r.yield_brut_pct,0)/DEMO_YIELD.length).toFixed(2)}%</div>
          <div className="kpi-sub">{yield_.results?.[0]?.city||"Tunis"}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Top negotiable</div>
          <div className="kpi-value" style={{color:"var(--warn)"}}>{nego.length>0?Math.round(nego[0]?.negociation_score*100):72}%</div>
          <div className="kpi-sub">Negotiation score</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Current window</div>
          <div className="kpi-value" style={{color:window_.current_verdict==="favorable"?"var(--ok)":window_.current_verdict==="unfavorable"?"var(--bad)":"var(--navy)"}}>{window_.current_verdict?.charAt(0).toUpperCase()+window_.current_verdict?.slice(1)||"—"}</div>
          <div className="kpi-sub">{window_.current_delta_pct>0?"+":""}{window_.current_delta_pct?.toFixed(1)}% vs avg.</div>
        </div>
      </div>

      {/* Sub-tabs */}
      <div className="dash-tabs">
        {SUB_TABS.map(t=>(
          <button key={t.id} className={subTab===t.id?"active":""} onClick={()=>setSubTab(t.id)}>
            {t.label}{t.count!==null&&<span style={{marginLeft:5,fontSize:10,opacity:.7}}>({t.count})</span>}
          </button>
        ))}
      </div>

      {/* Price Drops */}
      {subTab==="drops"&&(
        <div style={{display:"flex",flexDirection:"column",gap:14}}>
          <p style={{fontSize:12,color:"var(--mut)",padding:"6px 10px",background:"rgba(47,156,126,.06)",borderRadius:8,border:"1px solid rgba(47,156,126,.15)"}}>
            💡 These listings have dropped in price since first published. A drop = seller under pressure = negotiation power.
          </p>
          {drops.drops?.map((d:any)=>(
            <div key={d.title} className="opp-card">
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",gap:10}}>
                <div style={{flex:1}}>
                  <div style={{fontSize:14,fontWeight:600,color:"var(--txt)",marginBottom:3}}>{d.title}</div>
                  <div style={{fontSize:12,color:"var(--mut)"}}>{d.city} · {d.property_type} · {d.surface}m²</div>
                  <div style={{display:"flex",alignItems:"center",gap:10,marginTop:8}}>
                    <span style={{fontSize:12,color:"var(--mut)",textDecoration:"line-through"}}>{d.initial_price?.toLocaleString("en-US")} TND</span>
                    <span style={{fontSize:15,fontWeight:700,color:"var(--navy)"}}>{d.current_price?.toLocaleString("en-US")} TND</span>
                    <span style={{fontSize:12,fontWeight:700,color:"var(--ok)",background:"rgba(35,135,101,.1)",padding:"2px 8px",borderRadius:999}}>Trust {d.trust_score?.toFixed(2)}</span>
                  </div>
                </div>
                <div style={{textAlign:"right",flexShrink:0}}>
                  <div style={{fontFamily:"var(--font-display)",fontSize:22,fontWeight:700,color:"var(--bad)"}}>−{d.drop_pct?.toFixed(1)}%</div>
                  <div style={{fontSize:12,color:"var(--mut)"}}>−{d.drop_amount?.toLocaleString("en-US")} TND</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Rental Yield */}
      {subTab==="yield"&&(
        <div style={{display:"flex",flexDirection:"column",gap:14}}>
          <div className="panel" style={{padding:20}}>
            <div className="panel-head"><h3>Gross rental yield by city</h3></div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={yield_.results||DEMO_YIELD} barSize={28}>
                <XAxis dataKey="city" tick={{fill:"var(--mut)",fontSize:11}} axisLine={false} tickLine={false}/>
                <YAxis tickFormatter={v=>`${v}%`} tick={{fill:"var(--mut)",fontSize:10}} axisLine={false} tickLine={false}/>
                <Tooltip contentStyle={{background:"white",border:"1px solid var(--line)",borderRadius:10,fontSize:12}} formatter={(v:any)=>[`${v}%`,"Yield"]}/>
                <Bar dataKey="yield_brut_pct" radius={[4,4,0,0]}>
                  {(yield_.results||DEMO_YIELD).map((d:any,i:number)=><Cell key={i} fill={YC(d.yield_brut_pct)}/>)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="panel" style={{padding:0,overflow:"hidden"}}>
            <table>
              <thead><tr><th>City</th><th>Type</th><th>Median rent</th><th>Sale price</th><th>Gross yield</th><th>Net yield</th></tr></thead>
              <tbody>
                {(yield_.results||DEMO_YIELD).map((r:any)=>(
                  <tr key={r.city}>
                    <td style={{fontWeight:600}}>{r.city}</td>
                    <td style={{color:"var(--mut)",textTransform:"capitalize"}}>{r.property_type}</td>
                    <td>{r.median_rent?.toLocaleString("en-US")} TND/mo</td>
                    <td style={{fontFamily:"var(--font-display)",fontWeight:600}}>{r.median_sale_price?.toLocaleString("en-US")} TND</td>
                    <td><span style={{fontWeight:700,color:YC(r.yield_brut_pct)}}>{r.yield_brut_pct?.toFixed(2)}%</span></td>
                    <td style={{color:"var(--mut)"}}>{r.yield_net_pct?.toFixed(2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Negotiable */}
      {subTab==="nego"&&(
        <div style={{display:"flex",flexDirection:"column",gap:14}}>
          {nego.map((n:any)=>(
            <div key={n.title} className="opp-card">
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",gap:10}}>
                <div style={{flex:1}}>
                  <div style={{fontSize:14,fontWeight:600,marginBottom:3}}>{n.title}</div>
                  <div style={{fontSize:12,color:"var(--mut)",display:"flex",gap:10,flexWrap:"wrap"}}>
                    <span>📍 {n.city}</span>
                    <span><Clock size={10}/> {n.days_on_market} days on market</span>
                    <span style={{textTransform:"capitalize"}}>{n.seller_type?.replace("_"," ")}</span>
                  </div>
                  <div style={{marginTop:8,display:"flex",alignItems:"center",gap:8}}>
                    <span style={{fontSize:14,fontWeight:700,color:"var(--navy)"}}>{n.price?.toLocaleString("en-US")} TND</span>
                    <span style={{fontSize:12,color:"var(--ok)",fontWeight:700}}>
                      Estimated reduction: −{n.estimated_reduction_pct?.toFixed(1)}%
                    </span>
                  </div>
                </div>
                <div style={{textAlign:"center",flexShrink:0}}>
                  <div style={{fontSize:22,fontWeight:700,color:NS(n.negociation_score)}}>{Math.round(n.negociation_score*100)}%</div>
                  <div style={{fontSize:9,color:"var(--mut)",textTransform:"uppercase",letterSpacing:".05em"}}>Negotiation</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Buying Window */}
      {subTab==="window"&&(
        <div style={{display:"flex",flexDirection:"column",gap:14}}>
          <div className="panel" style={{padding:20}}>
            <div className="panel-head">
              <h3>Price seasonality by month</h3>
              <div style={{fontSize:12,color:window_.current_verdict==="favorable"?"var(--ok)":window_.current_verdict==="unfavorable"?"var(--bad)":"var(--navy)",fontWeight:700}}>
                Current: {window_.current_month} — {window_.current_verdict}
              </div>
            </div>
            <div style={{fontSize:12,color:"var(--mut)",lineHeight:1.6,marginBottom:14,padding:"10px 14px",background:"rgba(47,156,126,.06)",borderRadius:8,border:"1px solid rgba(47,156,126,.15)"}}>
              {window_.recommendation}
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={window_.monthly_index||[]} barSize={22}>
                <XAxis dataKey="month_name" tick={{fill:"var(--mut)",fontSize:9}} axisLine={false} tickLine={false}/>
                <YAxis tickFormatter={v=>`${v}%`} tick={{fill:"var(--mut)",fontSize:10}} axisLine={false} tickLine={false}/>
                <ReferenceLine y={0} stroke="var(--line)" strokeWidth={1}/>
                <Tooltip contentStyle={{background:"white",border:"1px solid var(--line)",borderRadius:10,fontSize:12}} formatter={(v:any)=>[`${v>0?"+":""}${v}%`,"vs average"]}/>
                <Bar dataKey="delta_vs_avg" radius={[3,3,0,0]}>
                  {(window_.monthly_index||[]).map((d:any,i:number)=><Cell key={i} fill={BAR(d.delta_vs_avg)}/>)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
