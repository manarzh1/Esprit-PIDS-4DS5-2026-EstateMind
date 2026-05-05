"use client";
import { useEffect, useState, useCallback } from "react";
import { TrendingUp, TrendingDown, Minus, AlertTriangle, Bell, RefreshCw, ChevronRight } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from "recharts";

interface ZoneAlert {
  zone:string; zone_type:string; alert_type:string; severity:"critical"|"high"|"medium";
  price_growth:number|null; volume_growth:number|null; emergence_score:number;
  n_listings_recent:number; n_listings_previous:number;
  median_price_recent:number|null; median_price_previous:number|null;
  message:string; recommendation:string; action_horizon_days:number;
}

const SEV_COLOR=(s:string)=>s==="critical"?"#cc3b25":s==="high"?"#bf7618":"#4a6fa5";

const ALERT_LABEL:Record<string,string>={
  emerging:"Emerging zone",price_surge:"Price surge",
  volume_surge:"Volume surge",declining:"Declining zone",
};
const ALERT_ICON:Record<string,string>={emerging:"🚀",price_surge:"📈",volume_surge:"📊",declining:"📉"};

const HORIZON_LABEL=(days:number)=>
  days<=30?"Act within 30 days":days<=45?"Act within 45 days":days<=90?"Act within 3 months":"Long-term horizon";

const DEMO_ALERTS:ZoneAlert[]=[
  {zone:"Hammamet",zone_type:"city",alert_type:"emerging",severity:"critical",
   price_growth:0.152,volume_growth:0.284,emergence_score:0.82,
   n_listings_recent:142,n_listings_previous:88,median_price_recent:380000,median_price_previous:330000,
   message:"Emerging zone: Hammamet — prices +15.2% and volume +28.4%.",
   recommendation:"High-potential zone: Hammamet records simultaneous price (+15.2%) and volume (+28.4%) growth. Opportunity window estimated at 30–60 days before alignment with neighbouring zones. Recommended for purchase or rental investment.",
   action_horizon_days:30},
  {zone:"Nabeul",zone_type:"city",alert_type:"price_surge",severity:"high",
   price_growth:0.122,volume_growth:0.081,emergence_score:0.63,
   n_listings_recent:98,n_listings_previous:72,median_price_recent:220000,median_price_previous:196000,
   message:"Price surge in Nabeul: +12.2%.",
   recommendation:"Strong price increase in Nabeul (+12.2%) without corresponding volume rise. Possible supply tension. If budget available, act within 45 days. Otherwise consider alternatives: Hammamet, Kélibia.",
   action_horizon_days:45},
  {zone:"Mahdia",zone_type:"city",alert_type:"volume_surge",severity:"medium",
   price_growth:0.041,volume_growth:0.312,emergence_score:0.44,
   n_listings_recent:61,n_listings_previous:47,median_price_recent:165000,median_price_previous:158000,
   message:"High activity in Mahdia: 61 listings (+31.2%).",
   recommendation:"Strong activity rebound in Mahdia (+31.2% listings). Growing attractiveness signal. Prices still stable: short-term opportunity for buyers and investors.",
   action_horizon_days:60},
  {zone:"Kasserine",zone_type:"city",alert_type:"declining",severity:"medium",
   price_growth:-0.093,volume_growth:-0.152,emergence_score:0.32,
   n_listings_recent:18,n_listings_previous:32,median_price_recent:85000,median_price_previous:93000,
   message:"Declining zone: Kasserine — −9.3% drop.",
   recommendation:"Declining zone in Kasserine (−9.3% prices). Not recommended for short-term investment. For residential buyers only with horizon > 5 years.",
   action_horizon_days:180},
];

const DEMO_TS=[
  {period:"Sep 25",median_price:290000,volume:412},{period:"Oct 25",median_price:295000,volume:441},
  {period:"Nov 25",median_price:300000,volume:388},{period:"Dec 25",median_price:298000,volume:356},
  {period:"Jan 26",median_price:305000,volume:502},{period:"Feb 26",median_price:314000,volume:534},
];

const DEMO_SPATIAL=[
  ["Tunis",{n_listings:1842,median_ppm2:2800}],["Sousse",{n_listings:1103,median_ppm2:2450}],
  ["Nabeul",{n_listings:874,median_ppm2:2200}],["Hammamet",{n_listings:742,median_ppm2:3800}],
  ["Sfax",{n_listings:631,median_ppm2:1950}],["Monastir",{n_listings:518,median_ppm2:2350}],
  ["Mahdia",{n_listings:312,median_ppm2:1650}],["Bizerte",{n_listings:287,median_ppm2:1480}],
];

function AlertCard({alert,expanded,onToggle}: {alert:ZoneAlert;expanded:boolean;onToggle:()=>void}) {
  const color=SEV_COLOR(alert.severity);
  return (
    <div style={{background:`${color}08`,border:`1px solid ${color}25`,borderRadius:12,marginBottom:10,overflow:"hidden",cursor:"pointer",boxShadow:"0 2px 8px rgba(7,29,51,.04)"}} onClick={onToggle}>
      <div style={{padding:"14px 18px",display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
        <div style={{display:"flex",alignItems:"flex-start",gap:10,flex:1}}>
          <span style={{fontSize:20,flexShrink:0}}>{ALERT_ICON[alert.alert_type]||"📌"}</span>
          <div style={{flex:1}}>
            <div style={{display:"flex",alignItems:"center",gap:8,flexWrap:"wrap",marginBottom:3}}>
              <span style={{fontSize:14,fontWeight:700}}>{alert.zone}</span>
              <span style={{fontSize:10,padding:"2px 8px",borderRadius:999,background:`${color}15`,color,fontWeight:700,border:`1px solid ${color}30`}}>
                {ALERT_LABEL[alert.alert_type]}
              </span>
              <span style={{fontSize:10,padding:"2px 8px",borderRadius:999,background:"rgba(7,29,51,.06)",color:"var(--mut)",fontWeight:600,textTransform:"capitalize"}}>
                {alert.severity}
              </span>
            </div>
            <p style={{fontSize:12,color:"var(--mut)",lineHeight:1.5}}>{alert.message}</p>
          </div>
        </div>
        <div style={{textAlign:"right",flexShrink:0,marginLeft:12}}>
          <div style={{fontFamily:"var(--font-display)",fontSize:24,fontWeight:700,color}}>{Math.round(alert.emergence_score*100)}</div>
          <div style={{fontSize:9,color:"var(--mut)",textTransform:"uppercase",letterSpacing:".05em"}}>score</div>
          <ChevronRight size={14} color="var(--mut)" style={{transform:expanded?"rotate(90deg)":"none",transition:"transform .2s",marginTop:4}}/>
        </div>
      </div>

      {expanded&&(
        <div style={{padding:"0 18px 16px",borderTop:`1px solid ${color}18`}}>
          <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:8,marginBottom:12}}>
            {[
              {l:"Price growth",v:alert.price_growth!=null?`${alert.price_growth>0?"+":""}${(alert.price_growth*100).toFixed(1)}%`:"—",c:alert.price_growth&&alert.price_growth>0?"var(--bad)":"var(--ok)"},
              {l:"Volume growth",v:alert.volume_growth!=null?`${alert.volume_growth>0?"+":""}${(alert.volume_growth*100).toFixed(1)}%`:"—",c:alert.volume_growth&&alert.volume_growth>0?"var(--ok)":"var(--bad)"},
              {l:"Current median",v:alert.median_price_recent?`${alert.median_price_recent.toLocaleString("en-US")} TND`:"—",c:"var(--navy)"},
              {l:"Recent listings",v:alert.n_listings_recent.toString(),c:"var(--navy)"},
              {l:"Previous listings",v:alert.n_listings_previous.toString(),c:"var(--mut)"},
              {l:"Action window",v:HORIZON_LABEL(alert.action_horizon_days),c:color},
            ].map(k=>(
              <div key={k.l} style={{background:"rgba(255,255,255,.7)",borderRadius:8,padding:"8px 10px"}}>
                <div style={{fontSize:9,color:"var(--mut)",textTransform:"uppercase",letterSpacing:".05em",marginBottom:2}}>{k.l}</div>
                <div style={{fontSize:12,fontWeight:700,color:k.c}}>{k.v}</div>
              </div>
            ))}
          </div>
          <div style={{background:"rgba(255,255,255,.8)",border:"1px solid rgba(255,255,255,.9)",borderRadius:8,padding:"10px 14px"}}>
            <div style={{fontSize:10,color:color,fontWeight:700,textTransform:"uppercase",letterSpacing:".06em",marginBottom:5}}>Recommendation</div>
            <p style={{fontSize:12,color:"var(--txt)",lineHeight:1.6}}>{alert.recommendation}</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function TerritorySection() {
  const [alerts,setAlerts]=useState<ZoneAlert[]>(DEMO_ALERTS);
  const [ts,setTs]=useState(DEMO_TS);
  const [spatial,setSpatial]=useState(DEMO_SPATIAL);
  const [loading,setLoading]=useState(false);
  const [expanded,setExpanded]=useState<string[]>([]);
  const [severity,setSeverity]=useState<"all"|"critical"|"high"|"medium">("all");

  const refresh=useCallback(async()=>{
    setLoading(true);
    try{const r=await fetch("/api/territorial/alerts?lookback_recent=45");if(r.ok){const d=await r.json();if(d?.alerts?.length)setAlerts(d.alerts);}}catch{}
    try{const r=await fetch("/api/territorial/timeseries");if(r.ok){const d=await r.json();if(d?.national?.length)setTs(d.national.slice(-6));}}catch{}
    try{const r=await fetch("/api/territorial/spatial");if(r.ok){const d=await r.json();if(d?.zones)setSpatial(Object.entries(d.zones).slice(0,8));}}catch{}
    setLoading(false);
  },[]);

  useEffect(()=>{refresh();},[]);

  const toggleExpand=(zone:string)=>setExpanded(e=>e.includes(zone)?e.filter(z=>z!==zone):[...zone,...e]);

  const critical=alerts.filter(a=>a.severity==="critical").length;
  const high=alerts.filter(a=>a.severity==="high").length;
  const emerging=alerts.filter(a=>a.alert_type==="emerging").length;
  const filtered=severity==="all"?alerts:alerts.filter(a=>a.severity===severity);

  return (
    <div style={{display:"flex",flexDirection:"column",gap:16}}>
      <div className="dash-topbar">
        <div>
          <h1>Territorial Dynamics</h1>
          <p>BO2 — Time series · Spatial aggregation · Emerging zones</p>
        </div>
        <button className="btn" onClick={refresh} disabled={loading}>
          <RefreshCw size={11} style={{animation:loading?"spin 1s linear infinite":"none"}}/>
          Refresh
        </button>
      </div>

      {/* KPIs */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">Critical alerts</div>
          <div className="kpi-value" style={{color:"var(--bad)"}}>{critical}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">High alerts</div>
          <div className="kpi-value" style={{color:"var(--warn)"}}>{high}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Emerging zones</div>
          <div className="kpi-value" style={{color:"var(--ok)"}}>{emerging}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Total alerts</div>
          <div className="kpi-value" style={{color:"var(--navy)"}}>{alerts.length}</div>
        </div>
      </div>

      <div style={{display:"grid",gridTemplateColumns:"1fr 340px",gap:14,alignItems:"start"}}>
        {/* Charts */}
        <div style={{display:"flex",flexDirection:"column",gap:14}}>
          <div className="panel">
            <div className="panel-head">
              <h3>Monthly evolution — national market</h3>
              <span style={{fontSize:11,color:"var(--mut)"}}>Mann-Kendall + linear regression</span>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={ts}>
                <XAxis dataKey="period" tick={{fill:"var(--mut)",fontSize:10}} axisLine={false} tickLine={false}/>
                <YAxis yAxisId="price" orientation="left" tick={{fill:"var(--mut)",fontSize:9}} axisLine={false} tickLine={false} tickFormatter={v=>`${Math.round(v/1000)}K`}/>
                <YAxis yAxisId="vol" orientation="right" tick={{fill:"var(--mut)",fontSize:9}} axisLine={false} tickLine={false}/>
                <Tooltip contentStyle={{background:"white",border:"1px solid var(--line)",borderRadius:10,fontSize:11}}
                  formatter={(v:any,name:string)=>[name==="median_price"?`${Number(v).toLocaleString("en-US")} TND`:v,name==="median_price"?"Median price":"Volume"]}/>
                <Line yAxisId="price" type="monotone" dataKey="median_price" stroke="#2f9c7e" strokeWidth={2.5} dot={{fill:"#2f9c7e",r:3}}/>
                <Line yAxisId="vol" type="monotone" dataKey="volume" stroke="#bf7618" strokeWidth={1.5} strokeDasharray="5 3" dot={false}/>
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="panel">
            <div className="panel-head"><h3>Median price/m² by city (top 8)</h3></div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={DEMO_SPATIAL.map(([c,v]:any)=>({city:c,ppm2:v.median_ppm2,n:v.n_listings}))} layout="vertical" barSize={14}>
                <XAxis type="number" tick={{fill:"var(--mut)",fontSize:9}} axisLine={false} tickLine={false} tickFormatter={v=>`${v.toLocaleString("en-US")}`}/>
                <YAxis type="category" dataKey="city" tick={{fill:"var(--txt)",fontSize:10,fontWeight:600}} axisLine={false} tickLine={false} width={70}/>
                <Tooltip contentStyle={{background:"white",border:"1px solid var(--line)",borderRadius:8,fontSize:11}} formatter={(v:any)=>[`${Number(v).toLocaleString("en-US")} TND/m²`]}/>
                <Bar dataKey="ppm2" radius={[0,4,4,0]}>
                  {DEMO_SPATIAL.map((_:any,i:number)=><Cell key={i} fill={i===0?"#cc3b25":i<=2?"#bf7618":"#2f9c7e"}/>)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Alerts panel */}
        <div className="panel" style={{position:"sticky",top:20}}>
          <div className="panel-head" style={{marginBottom:12}}>
            <h3>Alerts & Recommendations</h3>
          </div>
          <div style={{display:"flex",gap:4,marginBottom:12,flexWrap:"wrap"}}>
            {(["all","critical","high","medium"] as const).map(s=>(
              <button key={s} className={`bo-tab${severity===s?" active":""}`} style={{fontSize:10,padding:"5px 10px"}} onClick={()=>setSeverity(s)}>
                {s.charAt(0).toUpperCase()+s.slice(1)}
              </button>
            ))}
          </div>
          <div style={{maxHeight:480,overflowY:"auto"}}>
            {filtered.map(a=>(
              <AlertCard key={a.zone} alert={a} expanded={expanded.includes(a.zone)} onToggle={()=>toggleExpand(a.zone)}/>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
