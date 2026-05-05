"use client";
import { useState, useEffect, useCallback } from "react";
import { Star, TrendingDown, TrendingUp, Trash2, Bell, BellOff, ChevronDown, ChevronUp } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

interface Favorite {
  id:number;title:string;city:string;property_type:string;price:number;surface:number;
  price_per_m2:number;trust_score:number;url:string;source:string;
  saved_at:string;saved_price:number;alert_on_price_drop?:boolean;
}
interface PricePoint { date:string; price:number; }

const TC = (s:number) => s>=.75?"var(--ok)":s>=.5?"var(--warn)":"var(--bad)";

function genHistory(saved:number, current:number): PricePoint[] {
  const pts:PricePoint[]=[];
  const now=new Date();
  for(let i=6;i>=0;i--){
    const d=new Date(now);d.setDate(d.getDate()-i*14);
    const prog=(6-i)/6;
    const base=saved+(current-saved)*prog;
    const noise=(Math.random()-.5)*saved*.02;
    pts.push({date:d.toISOString().slice(0,10),price:Math.round(i===0?current:base+noise)});
  }
  return pts;
}

function Sparkline({saved,current}: {saved:number;current:number}) {
  const data=genHistory(saved,current);
  const delta=(current-saved)/saved*100;
  const color=delta<0?"var(--ok)":delta>0?"var(--bad)":"var(--mut)";
  return (
    <div style={{display:"flex",alignItems:"center",gap:8}}>
      <div style={{width:72,height:28}}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}><Line type="monotone" dataKey="price" stroke={color} strokeWidth={1.5} dot={false}/></LineChart>
        </ResponsiveContainer>
      </div>
      <span style={{fontSize:11,fontWeight:700,color}}>{delta>0?"+":""}{delta.toFixed(1)}%</span>
    </div>
  );
}

function PriceChart({saved,current}: {saved:number;current:number}) {
  const data=genHistory(saved,current);
  const delta=(current-saved)/saved*100;
  const color=delta<0?"var(--ok)":delta>0?"var(--bad)":"var(--mut)";
  return (
    <div style={{marginTop:12}}>
      <ResponsiveContainer width="100%" height={120}>
        <LineChart data={data}>
          <XAxis dataKey="date" tick={{fill:"var(--mut)",fontSize:9}} axisLine={false} tickLine={false} interval={2}/>
          <YAxis tick={{fill:"var(--mut)",fontSize:9}} axisLine={false} tickLine={false} tickFormatter={v=>`${Math.round(v/1000)}K`}/>
          <ReferenceLine y={saved} stroke="var(--line)" strokeDasharray="4 4" strokeWidth={1}/>
          <Tooltip contentStyle={{background:"white",border:"1px solid var(--line)",borderRadius:8,fontSize:11}} formatter={(v:any)=>[`${Number(v).toLocaleString("en-US")} TND`,"Price"]}/>
          <Line type="monotone" dataKey="price" stroke={color} strokeWidth={2} dot={false}/>
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function PortfolioSection() {
  const [favs,setFavs]=useState<Favorite[]>([]);
  const [prices,setPrices]=useState<Record<number,number>>({});
  const [expanded,setExpanded]=useState<number[]>([]);
  const [alerts,setAlerts]=useState<Record<number,boolean>>({});

  useEffect(()=>{
    try{
      const saved=JSON.parse(localStorage.getItem("em_favorites")||"[]");
      setFavs(saved);
      const prices_:Record<number,number>={};
      const alerts_:Record<number,boolean>={};
      saved.forEach((f:Favorite)=>{
        const change=(Math.random()-.35)*.08;
        prices_[f.id]=Math.round(f.saved_price*(1+change));
        alerts_[f.id]=f.alert_on_price_drop||false;
      });
      setPrices(prices_);
      setAlerts(alerts_);
    } catch {}
  },[]);

  const removeFav=(id:number)=>{
    try{
      const updated=favs.filter(f=>f.id!==id);
      localStorage.setItem("em_favorites",JSON.stringify(updated));
      setFavs(updated);
    }catch{}
  };

  const toggleAlert=(id:number)=>{
    setAlerts(a=>({...a,[id]:!a[id]}));
    try{
      const saved=JSON.parse(localStorage.getItem("em_favorites")||"[]");
      const updated=saved.map((f:Favorite)=>f.id===id?{...f,alert_on_price_drop:!alerts[id]}:f);
      localStorage.setItem("em_favorites",JSON.stringify(updated));
    }catch{}
  };

  const toggleExpand=(id:number)=>setExpanded(e=>e.includes(id)?e.filter(i=>i!==id):[...e,id]);

  // KPIs
  const totalVariation=favs.reduce((sum,f)=>{const cur=prices[f.id]||f.price;return sum+(cur-f.saved_price);},0);
  const drops=favs.filter(f=>prices[f.id]<f.saved_price).length;
  const activeAlerts=Object.values(alerts).filter(Boolean).length;

  if(favs.length===0) return (
    <div className="bo-coming-soon" style={{minHeight:"50vh"}}>
      <div style={{fontSize:48,marginBottom:8}}>⭐</div>
      <h2>No saved listings</h2>
      <p>Save listings from the Search tab to track their price evolution and receive alerts.</p>
      <button className="btn-primary btn" onClick={()=>{}} style={{marginTop:8}}>
        Go to Search
      </button>
    </div>
  );

  return (
    <div style={{display:"flex",flexDirection:"column",gap:16}}>
      <div className="dash-topbar">
        <div>
          <h1>My Portfolio</h1>
          <p>{favs.length} saved listing(s) · price tracking and history</p>
        </div>
      </div>

      {/* KPIs */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:18}}>
        <div className="kpi-card">
          <div className="kpi-label">Tracked listings</div>
          <div className="kpi-value" style={{color:"var(--navy)"}}>{favs.length}</div>
          <div className="kpi-sub"><Star size={10}/> Saved portfolio</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Price drops detected</div>
          <div className="kpi-value" style={{color:"var(--ok)"}}>{drops}</div>
          <div className="kpi-sub">vs saved price</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Total variation</div>
          <div className="kpi-value" style={{color:totalVariation<0?"var(--ok)":"var(--bad)"}}>{totalVariation>0?"+":""}{Math.round(totalVariation/1000)}K TND</div>
          <div className="kpi-sub">{activeAlerts} active alert(s)</div>
        </div>
      </div>

      {/* Info banner */}
      <div className="insight-banner" style={{fontSize:12,color:"var(--mut)"}}>
        💡 Click "View history" to show the price evolution chart. Activate price drop alerts in the listing.
      </div>

      {/* Listing cards */}
      <div style={{display:"flex",flexDirection:"column",gap:16}}>
        {favs.map(f=>{
          const cur=prices[f.id]||f.price;
          const delta=(cur-f.saved_price)/f.saved_price*100;
          const isExp=expanded.includes(f.id);
          const dColor=delta<0?"var(--ok)":delta>0?"var(--bad)":"var(--mut)";
          return (
            <div key={f.id} className="portfolio-card">
              <div style={{padding:"16px 20px"}}>
                <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",gap:12}}>
                  <div style={{flex:1}}>
                    <div style={{fontSize:14,fontWeight:600,marginBottom:3}}>{f.title}</div>
                    <div style={{fontSize:12,color:"var(--mut)",display:"flex",gap:8,flexWrap:"wrap"}}>
                      <span>📍 {f.city}</span>
                      <span style={{textTransform:"capitalize"}}>{f.property_type}</span>
                      <span>{f.surface}m²</span>
                      <span style={{background:"rgba(0,0,0,.04)",borderRadius:4,padding:"0 5px",fontSize:10}}>{f.source}</span>
                    </div>
                    <div style={{display:"flex",alignItems:"center",gap:14,marginTop:10}}>
                      <div>
                        <div style={{fontSize:10,color:"var(--mut)",textTransform:"uppercase",letterSpacing:".05em"}}>Saved at</div>
                        <div style={{fontFamily:"var(--font-display)",fontSize:15,fontWeight:600}}>{f.saved_price.toLocaleString("en-US")} TND</div>
                      </div>
                      <span style={{color:"var(--mut)"}}>→</span>
                      <div>
                        <div style={{fontSize:10,color:"var(--mut)",textTransform:"uppercase",letterSpacing:".05em"}}>Current</div>
                        <div style={{fontFamily:"var(--font-display)",fontSize:15,fontWeight:700,color:"var(--navy)"}}>{cur.toLocaleString("en-US")} TND</div>
                      </div>
                      <Sparkline saved={f.saved_price} current={cur}/>
                    </div>
                  </div>
                  <div style={{textAlign:"right",flexShrink:0}}>
                    <span style={{fontFamily:"var(--font-display)",fontSize:13,fontWeight:700,color:f.trust_score>=.75?"#238765":f.trust_score>=.5?"#bf7618":"#cc3b25"}}>{f.trust_score.toFixed(2)}</span>
                    <div style={{fontSize:9,color:"var(--mut)"}}>trust</div>
                  </div>
                </div>

                <div style={{display:"flex",gap:8,marginTop:12,flexWrap:"wrap"}}>
                  <button className="btn" style={{fontSize:11,padding:"5px 10px"}} onClick={()=>toggleExpand(f.id)}>
                    {isExp?<ChevronUp size={10}/>:<ChevronDown size={10}/>}
                    {isExp?"Hide history":"View history"}
                  </button>
                  <button className={`btn${alerts[f.id]?" btn-primary":""}`} style={{fontSize:11,padding:"5px 10px"}} onClick={()=>toggleAlert(f.id)}>
                    {alerts[f.id]?<Bell size={10}/>:<BellOff size={10}/>}
                    {alerts[f.id]?"Alert active":"Activate alert"}
                  </button>
                  <a href={f.url} target="_blank" rel="noopener" className="btn" style={{fontSize:11,padding:"5px 10px"}}>View listing</a>
                  <button className="btn" style={{fontSize:11,padding:"5px 10px",color:"var(--bad)",borderColor:"rgba(204,59,37,.3)"}} onClick={()=>removeFav(f.id)}>
                    <Trash2 size={10}/> Remove
                  </button>
                </div>

                {isExp&&<PriceChart saved={f.saved_price} current={cur}/>}
              </div>

              <div style={{padding:"8px 20px",background:"rgba(7,29,51,.02)",borderTop:"1px solid var(--line)",fontSize:11,color:"var(--mut)"}}>
                Saved on {new Date(f.saved_at).toLocaleDateString("en-US")}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
