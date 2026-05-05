"use client";
import { useState, useCallback } from "react";
import { Search, SlidersHorizontal, X, ExternalLink, Star, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { DEMO_LISTINGS as LISTINGS, filterListings, type Listing } from "@/lib/demo-listings";

const TC=(s:number)=>s>=.75?"#238765":s>=.5?"#bf7618":"#cc3b25";
const LC=(s:number)=>s<.3?"#238765":s<.6?"#bf7618":"#cc3b25";

function saveFav(r:Listing){
  try{
    const f=JSON.parse(localStorage.getItem("em_favorites")||"[]");
    if(!f.find((x:any)=>x.id===r.id)){f.push({...r,saved_at:new Date().toISOString(),saved_price:r.price});localStorage.setItem("em_favorites",JSON.stringify(f));alert(`"${r.title.slice(0,40)}..." saved to portfolio!`);}
    else alert("Already in your portfolio.");
  }catch{}
}

function PriceFairness({price,surface,city}:{price:number;surface:number;city:string}){
  const [res,setRes]=useState<any>(null);const [loading,setLoading]=useState(false);
  const check=useCallback(async()=>{
    if(!price||!surface)return;setLoading(true);
    const ppm2=price/surface;let med=2200;
    try{const r=await fetch(`/api/market?city=${encodeURIComponent(city)}`);if(r.ok){const d=await r.json();const c=d.cities?.find((x:any)=>x.city?.toLowerCase()===city.toLowerCase());if(c?.median)med=c.median;}}catch{}
    const delta=(med-ppm2)/med*100;const verdict=delta>10?"undervalued":delta<-10?"overvalued":"fair";
    const color=verdict==="undervalued"?"#238765":verdict==="overvalued"?"#cc3b25":"#bf7618";
    setRes({verdict,delta,ppm2:Math.round(ppm2),med:Math.round(med),color,msg:verdict==="undervalued"?`${delta.toFixed(1)}% below ${city} median.`:verdict==="overvalued"?`${Math.abs(delta).toFixed(1)}% above ${city} median — negotiate.`:`Consistent with ${city} market.`});
    setLoading(false);
  },[price,surface,city]);
  if(!res&&!loading)return(<button onClick={check} style={{fontSize:11,padding:"5px 12px",borderRadius:8,border:"1px solid rgba(47,156,126,.35)",background:"rgba(47,156,126,.08)",color:"#2f9c7e",cursor:"pointer",fontFamily:"Inter,sans-serif",fontWeight:700}}>Is this price fair?</button>);
  if(loading)return<span style={{fontSize:11,color:"#6e7a8a"}}>Analysing...</span>;
  if(!res)return null;
  return(
    <div style={{background:`${res.color}08`,border:`1px solid ${res.color}25`,borderRadius:10,padding:"10px 12px",marginTop:8}}>
      <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:4}}>{res.verdict==="undervalued"?<TrendingDown size={12} color={res.color}/>:res.verdict==="overvalued"?<TrendingUp size={12} color={res.color}/>:<Minus size={12} color={res.color}/>}<span style={{fontSize:12,fontWeight:700,color:res.color}}>{res.verdict.toUpperCase()}</span></div>
      <p style={{fontSize:11,color:"#0b1d33",margin:"0 0 8px"}}>{res.msg}</p>
      <div style={{display:"flex",gap:8}}>
        {[{l:"Price/m²",v:`${res.ppm2} TND`,c:res.color},{l:"Market",v:`${res.med} TND`,c:"#6e7a8a"},{l:"Gap",v:`${Math.abs(res.delta).toFixed(1)}%`,c:res.color}].map(k=>(
          <div key={k.l} style={{flex:1,background:"rgba(7,29,51,.04)",borderRadius:6,padding:"6px 8px",textAlign:"center"}}>
            <div style={{fontSize:12,fontWeight:700,color:k.c}}>{k.v}</div><div style={{fontSize:9,color:"#6e7a8a"}}>{k.l}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AnalysisPanel({listing,onClose}:{listing:Listing;onClose:()=>void}){
  const [status,setStatus]=useState<"loading"|"done"|"error">("loading");
  const [result,setResult]=useState<any>(null);
  useState(()=>{
    let active=true;
    (async()=>{
      try{
        const resp=await fetch("/api/analyze",{method:"POST",headers:{"Content-Type":"application/json"},
          body:JSON.stringify({description:listing.description||listing.title,price:listing.price,surface:listing.surface,city:listing.city,property_type:listing.property_type,source:listing.source}),
          signal:AbortSignal.timeout(8000)});
        if(!active)return;
        if(resp.ok){setResult(await resp.json());setStatus("done");}else setStatus("error");
      }catch{if(active)setStatus("error");}
    })();
    return()=>{active=false;};
  });
  const vc=result?{"FAVORABLE":"#238765","ATTENTION":"#bf7618","DANGER":"#cc3b25"}[result.verdict as string]||"#6e7a8a":null;
  return(
    <div style={{background:"rgba(255,255,255,.92)",border:"1px solid rgba(255,255,255,.95)",borderRadius:20,padding:20,position:"sticky",top:20,boxShadow:"0 8px 28px rgba(7,29,51,.1)"}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:12}}>
        <span style={{fontSize:14,fontWeight:700,color:"#071d33"}}>AI Analysis</span>
        <button onClick={onClose} style={{background:"none",border:"none",cursor:"pointer",color:"#6e7a8a",fontSize:22,lineHeight:1}}>×</button>
      </div>
      <div style={{fontSize:11,color:"#6e7a8a",marginBottom:12,padding:"6px 10px",background:"rgba(7,29,51,.04)",borderRadius:8,lineHeight:1.5}}>{listing.title.slice(0,60)}…</div>
      {status==="loading"&&(<div style={{display:"flex",flexDirection:"column",alignItems:"center",gap:12,padding:"24px 0"}}><div style={{width:32,height:32,border:"3px solid #e6eaf0",borderTop:"3px solid #2f9c7e",borderRadius:"50%",animation:"spin 1s linear infinite"}}/><span style={{fontSize:12,color:"#6e7a8a"}}>Analysing with AI…</span></div>)}
      {status==="error"&&(<div style={{background:"rgba(204,59,37,.05)",border:"1px solid rgba(204,59,37,.18)",borderRadius:10,padding:"14px",textAlign:"center"}}><div style={{fontSize:22,marginBottom:6}}>⚠️</div><div style={{fontSize:12,fontWeight:700,color:"#cc3b25",marginBottom:4}}>Backend not reachable</div><div style={{fontSize:11,color:"#6e7a8a",marginBottom:12,lineHeight:1.5}}>Start FastAPI on port 8000 to enable AI analysis.</div><div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>{[{l:"Trust",v:listing.trust_score.toFixed(3),c:"#238765"},{l:"Legal risk",v:listing.legal_risk_score.toFixed(3),c:"#bf7618"}].map(k=>(<div key={k.l} style={{background:"white",borderRadius:8,padding:"8px"}}><div style={{fontSize:9,color:"#6e7a8a",marginBottom:2,textTransform:"uppercase"}}>{k.l}</div><div style={{fontSize:16,fontWeight:700,color:k.c}}>{k.v}</div></div>))}</div></div>)}
      {status==="done"&&result&&vc&&(<div style={{display:"flex",flexDirection:"column",gap:10}}><div style={{background:`${vc}10`,border:`1px solid ${vc}28`,borderRadius:12,padding:"12px 14px"}}><div style={{fontSize:15,fontWeight:800,color:vc,marginBottom:4}}>{result.verdict}</div><div style={{fontSize:11,color:"#6e7a8a",lineHeight:1.6}}>{result.recommendation}</div></div><div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>{[{l:"Trust",v:result.trust_score?.toFixed(3),c:"#238765"},{l:"Legal risk",v:result.legal_risk_score?.toFixed(3),c:"#bf7618"}].map(k=>(<div key={k.l} style={{background:"rgba(7,29,51,.03)",borderRadius:8,padding:"8px"}}><div style={{fontSize:9,color:"#6e7a8a",textTransform:"uppercase",marginBottom:2}}>{k.l}</div><div style={{fontSize:16,fontWeight:700,color:k.c}}>{k.v}</div></div>))}{result.price_analysis&&(<div style={{gridColumn:"span 2",fontSize:11,color:"#6e7a8a",padding:"8px",background:"rgba(7,29,51,.03)",borderRadius:8}}>{result.price_analysis}</div>)}</div></div>)}
    </div>
  );
}

function ListingCard({r,selected,onSelect,onAnalyze}:{r:Listing;selected:boolean;onSelect:()=>void;onAnalyze:(r:Listing)=>void}){
  const [exp,setExp]=useState(false);const c=TC(r.trust_score);
  const BTN={display:"inline-flex",alignItems:"center",gap:5,padding:"7px 12px",borderRadius:10,border:"1px solid #e6eaf0",background:"white",color:"#6e7a8a",fontSize:12,fontWeight:700,cursor:"pointer",fontFamily:"Inter,sans-serif"} as const;
  return(
    <div className={`listing-card${selected?" selected":""}`}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",gap:12}}>
        <div style={{display:"flex",alignItems:"flex-start",gap:10,flex:1}}>
          <input type="checkbox" checked={selected} onChange={onSelect} style={{marginTop:4,width:16,height:16,accentColor:"#2f9c7e",cursor:"pointer",flexShrink:0}}/>
          <div style={{flex:1}}>
            <div style={{fontSize:14,fontWeight:700,color:"#0b1d33",marginBottom:3}}>{r.title}</div>
            <div style={{fontSize:12,color:"#6e7a8a",display:"flex",gap:8,flexWrap:"wrap"}}>
              <span>📍 {r.city}</span><span style={{textTransform:"capitalize"}}>{r.property_type}</span><span>{r.surface}m²</span>
              <span style={{background:"rgba(7,29,51,.07)",borderRadius:4,padding:"1px 6px",fontSize:11,fontWeight:600}}>{r.source}</span>
            </div>
          </div>
        </div>
        <div style={{textAlign:"right",flexShrink:0}}>
          <div style={{fontFamily:"Georgia,serif",fontSize:17,fontWeight:700,color:"#071d33"}}>{r.price.toLocaleString("en-US")} TND</div>
          <div style={{fontSize:11,color:"#6e7a8a"}}>{r.price_per_m2.toLocaleString("en-US")} TND/m²</div>
          <div style={{display:"flex",alignItems:"center",gap:5,marginTop:5,justifyContent:"flex-end"}}>
            <div style={{width:38,height:4,background:"#e6eaf0",borderRadius:2,overflow:"hidden"}}><div style={{height:"100%",width:`${r.trust_score*100}%`,background:c,borderRadius:2}}/></div>
            <span style={{fontSize:12,fontWeight:700,color:c}}>{r.trust_score.toFixed(2)}</span>
          </div>
        </div>
      </div>
      <div style={{display:"flex",gap:8,marginTop:12,flexWrap:"wrap"}}>
        <button onClick={()=>setExp(e=>!e)} style={BTN}>{exp?"▲":"▼"} Details</button>
        <button onClick={()=>onAnalyze(r)} style={{...BTN,background:"linear-gradient(135deg,#2f9c7e,#1e7d63)",color:"white",border:"none",boxShadow:"0 4px 12px rgba(47,156,126,.28)",fontWeight:800}}>Analyse AI</button>
        <a href={r.url} target="_blank" rel="noopener" style={{...BTN,textDecoration:"none"}}><ExternalLink size={11}/> View</a>
        <button onClick={()=>saveFav(r)} style={BTN}><Star size={11}/> Save</button>
      </div>
      {exp&&(
        <div style={{marginTop:14,borderTop:"1px solid #e6eaf0",paddingTop:14}}>
          {r.description&&<p style={{fontSize:12,color:"#6e7a8a",lineHeight:1.6,marginBottom:12}}>{r.description}</p>}
          <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:8,marginBottom:12}}>
            {[{l:"Price",v:`${r.price.toLocaleString("en-US")} TND`},{l:"Price/m²",v:`${r.price_per_m2.toLocaleString("en-US")} TND`},{l:"Surface",v:`${r.surface} m²`},{l:"Trust",v:r.trust_score.toFixed(3),c:TC(r.trust_score)},{l:"Legal risk",v:r.legal_risk_score.toFixed(3),c:LC(r.legal_risk_score)},{l:"Source",v:r.source}].map(k=>(
              <div key={k.l} style={{background:"rgba(7,29,51,.03)",borderRadius:8,padding:"8px 10px"}}><div style={{fontSize:9,color:"#6e7a8a",textTransform:"uppercase",letterSpacing:".05em",marginBottom:2}}>{k.l}</div><div style={{fontSize:13,fontWeight:700,color:(k as any).c||"#0b1d33"}}>{k.v}</div></div>
            ))}
          </div>
          <PriceFairness price={r.price} surface={r.surface} city={r.city}/>
        </div>
      )}
    </div>
  );
}

export default function SearchSection(){
  const [q,setQ]=useState("");const [city,setCity]=useState("");const [ptype,setPtype]=useState("");
  const [pmin,setPmin]=useState("");const [pmax,setPmax]=useState("");const [smin,setSmin]=useState("");
  const [tmin,setTmin]=useState("0");const [sort,setSort]=useState("trust_score");
  const [showF,setShowF]=useState(false);
  const [results,setResults]=useState<Listing[]>(LISTINGS.slice(0,20));
  const [loading,setLoading]=useState(false);
  const [analyzing,setAnalyzing]=useState<Listing|null>(null);
  const [selected,setSelected]=useState<number[]>([]);

  const search=useCallback(async()=>{
    setLoading(true);
    // Always run local filter (instant, always works)
    const local=filterListings(LISTINGS,q,city,ptype,pmin,pmax,smin,tmin,sort);
    setResults(local);
    // Try API (real backend data if available)
    try{
      const p=new URLSearchParams();
      if(q)p.set("q",q);if(city)p.set("city",city);if(ptype)p.set("property_type",ptype);
      if(pmin)p.set("price_min",pmin);if(pmax)p.set("price_max",pmax);if(smin)p.set("surface_min",smin);
      if(tmin&&tmin!=="0")p.set("trust_min",tmin);if(sort)p.set("sort_by",sort);
      const r=await fetch(`/api/search?${p}`,{signal:AbortSignal.timeout(2500)});
      if(r.ok){const d=await r.json();if(d.results?.length>0)setResults(d.results);}
    }catch{}
    setLoading(false);
  },[q,city,ptype,pmin,pmax,smin,tmin,sort]);

  const reset=()=>{setQ("");setCity("");setPtype("");setPmin("");setPmax("");setSmin("");setTmin("0");setSort("trust_score");setResults(LISTINGS.slice(0,20));};
  const toggleSel=(id:number)=>setSelected(p=>p.includes(id)?p.filter(i=>i!==id):p.length<4?[...p,id]:p);
  const IS={padding:"9px 12px",borderRadius:10,fontSize:13,border:"1px solid #e6eaf0",background:"white",color:"#0b1d33",fontFamily:"Inter,sans-serif",width:"100%",outline:"none"} as const;

  // Unique cities for autocomplete display
  const cities=[...new Set(LISTINGS.map(l=>l.city))].sort();

  return(
    <div style={{display:"flex",flexDirection:"column",gap:16}}>
      <div>
        <h2 style={{fontFamily:"Georgia,serif",fontSize:24,fontWeight:600,marginBottom:4}}>Listing Search</h2>
        <p style={{fontSize:13,color:"#6e7a8a"}}>{results.length} result(s) · check to compare · "Fair Price?" in Details</p>
      </div>

      <div style={{display:"flex",gap:10,flexWrap:"wrap",alignItems:"center"}}>
        <div style={{flex:1,minWidth:220,display:"flex",alignItems:"center",gap:10,padding:"0 14px",height:46,background:"rgba(255,255,255,.85)",border:"1px solid rgba(230,234,240,.9)",borderRadius:14,boxShadow:"0 8px 20px rgba(7,29,51,.06)"}}>
          <Search size={14} color="#6e7a8a"/>
          <input value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==="Enter"&&search()} placeholder="City, type, keyword... (Enter)"
            style={{flex:1,border:0,outline:0,background:"transparent",fontWeight:600,fontSize:13,color:"#0b1d33",fontFamily:"Inter,sans-serif"}}/>
          {q&&<button onClick={()=>{setQ("");setResults(LISTINGS.slice(0,20));}} style={{background:"none",border:"none",cursor:"pointer",color:"#6e7a8a"}}><X size={12}/></button>}
        </div>
        <button onClick={()=>setShowF(s=>!s)} style={{display:"inline-flex",alignItems:"center",gap:6,padding:"0 16px",height:46,borderRadius:14,border:`1px solid ${showF?"rgba(47,156,126,.4)":"#e6eaf0"}`,background:showF?"rgba(47,156,126,.08)":"white",color:showF?"#2f9c7e":"#6e7a8a",cursor:"pointer",fontSize:13,fontWeight:700,fontFamily:"Inter,sans-serif"}}>
          <SlidersHorizontal size={14}/>Filters
        </button>
        <button onClick={search} style={{display:"inline-flex",alignItems:"center",height:46,padding:"0 22px",borderRadius:14,border:"none",background:"linear-gradient(135deg,#2f9c7e,#1e7d63)",color:"white",cursor:"pointer",fontSize:13,fontWeight:800,fontFamily:"Inter,sans-serif",boxShadow:"0 8px 20px rgba(47,156,126,.28)",opacity:loading?.7:1}}>
          {loading?"…":"Search"}
        </button>
      </div>

      {showF&&(
        <div style={{background:"rgba(255,255,255,.88)",border:"1px solid rgba(255,255,255,.95)",borderRadius:18,padding:18,boxShadow:"0 8px 24px rgba(7,29,51,.06)"}}>
          <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:10,marginBottom:12}}>
            <div>
              <label style={{fontSize:10,color:"#6e7a8a",display:"block",marginBottom:4,textTransform:"uppercase",letterSpacing:".06em",fontWeight:700}}>City</label>
              <input value={city} onChange={e=>setCity(e.target.value)} list="city-list" placeholder="e.g. Sousse" style={IS}/>
              <datalist id="city-list">{cities.map(c=><option key={c} value={c}/>)}</datalist>
            </div>
            {[
              {l:"Type",el:<select value={ptype} onChange={e=>setPtype(e.target.value)} style={IS}><option value="">All types</option>{["apartment","villa","land","house","studio","commercial"].map(t=><option key={t}>{t}</option>)}</select>},
              {l:"Min price",el:<input type="number" value={pmin} onChange={e=>setPmin(e.target.value)} placeholder="e.g. 100000" style={IS}/>},
              {l:"Max price",el:<input type="number" value={pmax} onChange={e=>setPmax(e.target.value)} placeholder="e.g. 500000" style={IS}/>},
              {l:"Min surface",el:<input type="number" value={smin} onChange={e=>setSmin(e.target.value)} placeholder="e.g. 80" style={IS}/>},
              {l:"Min trust",el:<select value={tmin} onChange={e=>setTmin(e.target.value)} style={IS}><option value="0">All</option><option value="0.5">≥ 0.50 Moderate</option><option value="0.75">≥ 0.75 Reliable</option></select>},
              {l:"Sort by",el:<select value={sort} onChange={e=>setSort(e.target.value)} style={IS}><option value="trust_score">Trust ↓</option><option value="price_asc">Price ↑</option><option value="price_desc">Price ↓</option></select>},
            ].map(f=>(
              <div key={f.l}><label style={{fontSize:10,color:"#6e7a8a",display:"block",marginBottom:4,textTransform:"uppercase",letterSpacing:".06em",fontWeight:700}}>{f.l}</label>{f.el}</div>
            ))}
          </div>
          <div style={{display:"flex",gap:8}}>
            <button onClick={search} style={{padding:"8px 18px",borderRadius:10,border:"none",background:"linear-gradient(135deg,#2f9c7e,#1e7d63)",color:"white",fontSize:12,fontWeight:800,cursor:"pointer",fontFamily:"Inter,sans-serif"}}>Apply</button>
            <button onClick={reset} style={{padding:"8px 14px",borderRadius:10,border:"1px solid #e6eaf0",background:"transparent",color:"#6e7a8a",fontSize:12,cursor:"pointer",fontFamily:"Inter,sans-serif"}}>Reset</button>
          </div>
        </div>
      )}

      <div style={{display:"grid",gridTemplateColumns:analyzing?"1fr 290px":"1fr",gap:16,alignItems:"start"}}>
        <div>
          {results.length===0
            ?<div style={{textAlign:"center",padding:"48px 0",color:"#6e7a8a"}}>No results. Try different filters.</div>
            :results.map(r=><ListingCard key={r.id} r={r} selected={selected.includes(r.id)} onSelect={()=>toggleSel(r.id)} onAnalyze={setAnalyzing}/>)
          }
        </div>
        {analyzing&&<AnalysisPanel listing={analyzing} onClose={()=>setAnalyzing(null)}/>}
      </div>
    </div>
  );
}
