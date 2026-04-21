"use client";
import { useState, useCallback } from "react";
import { Search, SlidersHorizontal, MapPin, Shield, X, ExternalLink, Star, GitCompare, CheckSquare, Square, TrendingUp, TrendingDown, Minus, Info } from "lucide-react";

interface Listing { id:number; title:string; city:string; property_type:string; price:number; surface:number; price_per_m2:number; trust_score:number; trust_level:string; legal_risk_score:number; url:string; source:string; description?:string; }

const DEMO: Listing[] = [
  {id:1,title:"Appartement S+3 La Marsa 120m²",   city:"La Marsa", property_type:"appartement",price:315000,surface:120,price_per_m2:2625,trust_score:0.84,trust_level:"Fiable", legal_risk_score:0.12,url:"https://tayara.tn/1",  source:"tayara",   description:"Appartement rénové, acte notarié, vue mer."},
  {id:2,title:"Villa S+4 Hammamet Nord piscine",   city:"Hammamet", property_type:"villa",       price:520000,surface:240,price_per_m2:2166,trust_score:0.77,trust_level:"Fiable", legal_risk_score:0.18,url:"https://mubawab.tn/2", source:"mubawab",  description:"Grande villa piscine, titre foncier."},
  {id:3,title:"Terrain 400m² Nabeul zone urbaine", city:"Nabeul",   property_type:"terrain",     price:95000, surface:400,price_per_m2:237, trust_score:0.31,trust_level:"Suspect",legal_risk_score:0.72,url:"https://tayara.tn/3",  source:"tayara",   description:"Terrain constructible, situation irrégulière."},
  {id:4,title:"Appartement S+2 Sousse vue mer",   city:"Sousse",   property_type:"appartement",price:215000,surface:95, price_per_m2:2263,trust_score:0.72,trust_level:"Moyen",  legal_risk_score:0.28,url:"https://tecnocasa.tn/4",source:"tecnocasa",description:"Bien situé à 200m de la plage."},
  {id:5,title:"Studio meublé centre Tunis",        city:"Tunis",    property_type:"studio",      price:130000,surface:52, price_per_m2:2500,trust_score:0.91,trust_level:"Fiable", legal_risk_score:0.09,url:"https://remax.tn/5",   source:"remax",    description:"Studio équipé, acte notarié."},
  {id:6,title:"Maison R+1 Bizerte 140m²",          city:"Bizerte",  property_type:"maison",      price:195000,surface:140,price_per_m2:1392,trust_score:0.69,trust_level:"Moyen",  legal_risk_score:0.33,url:"https://mubawab.tn/6", source:"mubawab",  description:"Maison familiale, grand jardin."},
  {id:7,title:"Appartement S+2 Monastir",          city:"Monastir", property_type:"appartement",price:210000,surface:90, price_per_m2:2333,trust_score:0.82,trust_level:"Fiable", legal_risk_score:0.14,url:"https://tecnocasa.tn/7",source:"tecnocasa",description:"Résidence sécurisée, parking."},
  {id:8,title:"Local commercial Sfax centre",      city:"Sfax",     property_type:"bureau_local",price:320000,surface:180,price_per_m2:1777,trust_score:0.61,trust_level:"Moyen",  legal_risk_score:0.43,url:"https://tayara.tn/8",  source:"tayara",   description:"Local vitrine, fort passage."},
];
const TC  = (s:number) => s>=.75?"#52C896":s>=.5?"#E8A84C":"#E05C5C";
const LC  = (s:number) => s<.3?"#52C896":s<.6?"#E8A84C":"#E05C5C";
const IS  = {padding:"7px 10px",borderRadius:7,fontSize:12,border:"1px solid var(--bor)",background:"var(--el)",color:"var(--txt)",fontFamily:"var(--font-body)",width:"100%"} as const;

function saveFav(r:Listing){ try{ const f=JSON.parse(localStorage.getItem("em_favorites")||"[]"); if(!f.find((x:any)=>x.id===r.id)){f.push({...r,saved_at:new Date().toISOString(),saved_price:r.price});localStorage.setItem("em_favorites",JSON.stringify(f));alert(`"${r.title.slice(0,35)}..." ajouté au portefeuille !`);}else alert("Déjà dans votre portefeuille.");}catch{}}

// ── Widget Prix Juste (inline) ────────────────────────────────────────────────
function PriceFairness({ price, surface, city, property_type }: { price:number; surface:number; city:string; property_type:string }) {
  const [res, setRes] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const computed = useCallback(async () => {
    if (!price || !surface) return;
    setLoading(true);
    const ppm2 = price / surface;
    let medianPpm2 = 2200;
    try {
      const r = await fetch(`/api/market?city=${encodeURIComponent(city)}`);
      if (r.ok) { const d = await r.json(); const c = d.cities?.find((x:any)=>x.city?.toLowerCase()===city.toLowerCase()); if(c?.median) medianPpm2=c.median; }
    } catch {}
    const delta = (medianPpm2 - ppm2) / medianPpm2 * 100;
    const verdict = delta > 10 ? "sous-évalué" : delta < -10 ? "sur-évalué" : "juste";
    const color   = verdict==="sous-évalué" ? "#1D9E75" : verdict==="sur-évalué" ? "#E24B4A" : "var(--gold)";
    setRes({ verdict, delta, ppm2: Math.round(ppm2), medianPpm2: Math.round(medianPpm2), color,
      msg: verdict==="sous-évalué" ? `${delta.toFixed(1)}% sous la médiane à ${city} — opportunité potentielle.`
           : verdict==="sur-évalué"  ? `${Math.abs(delta).toFixed(1)}% au-dessus de la médiane à ${city} — négociation possible.`
           : `Prix cohérent avec le marché à ${city} (écart ${Math.abs(delta).toFixed(1)}%).` });
    setLoading(false);
  }, [price, surface, city]);

  if (!res && !loading) return (
    <button onClick={computed} style={{ fontSize:11, padding:"5px 10px", borderRadius:6, border:"1px solid rgba(200,169,110,.3)", background:"rgba(200,169,110,.08)", color:"var(--gold)", cursor:"pointer", fontFamily:"var(--font-body)" }}>
      Ce prix est-il juste ?
    </button>
  );
  if (loading) return <span style={{ fontSize:11, color:"var(--mut)" }}>Analyse...</span>;
  if (!res) return null;
  return (
    <div style={{ background:`${res.color}08`, border:`1px solid ${res.color}25`, borderRadius:8, padding:"10px 12px", marginTop:8 }}>
      <div style={{ display:"flex", alignItems:"center", gap:6, marginBottom:6 }}>
        {res.verdict==="sous-évalué"?<TrendingDown size={12} color={res.color}/>:res.verdict==="sur-évalué"?<TrendingUp size={12} color={res.color}/>:<Minus size={12} color={res.color}/>}
        <span style={{ fontSize:12, fontWeight:600, color:res.color }}>{res.verdict.toUpperCase()}</span>
      </div>
      <p style={{ fontSize:11, color:"var(--txt)", lineHeight:1.5, margin:"0 0 8px" }}>{res.msg}</p>
      <div style={{ display:"flex", gap:8 }}>
        {[{l:"Prix/m² bien",val:`${res.ppm2} TND`,c:res.color},{l:"Médiane marché",val:`${res.medianPpm2} TND`,c:"var(--mut)"},{l:"Écart",val:`${res.delta>0?"-":"+"}${Math.abs(res.delta).toFixed(1)}%`,c:res.color}].map(k=>(
          <div key={k.l} style={{ flex:1, background:"var(--el)", borderRadius:6, padding:"6px 8px", textAlign:"center" }}>
            <div style={{ fontSize:12, fontWeight:600, fontFamily:"var(--font-display)", color:k.c }}>{k.val}</div>
            <div style={{ fontSize:9, color:"var(--mut)", marginTop:1 }}>{k.l}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Carte résultat ─────────────────────────────────────────────────────────────
function Card({ r, selected, onSelect, onAnalyze }: { r:Listing; selected:boolean; onSelect:()=>void; onAnalyze:(r:Listing)=>void }) {
  const [exp, setExp] = useState(false);
  const [showFair, setShowFair] = useState(false);
  const c = TC(r.trust_score);
  return (
    <div style={{ background:"var(--card)", border:`1px solid ${selected?"var(--gold)":"var(--bor)"}`, borderRadius:10, padding:"14px 16px", marginBottom:8, transition:"border-color .15s" }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", gap:10 }}>
        <button onClick={onSelect} style={{ background:"none", border:"none", cursor:"pointer", color:selected?"var(--gold)":"var(--mut)", padding:"2px 4px 0 0", flexShrink:0 }}>
          {selected?<CheckSquare size={14} color="var(--gold)"/>:<Square size={14}/>}
        </button>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ fontSize:13, fontWeight:500, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis", marginBottom:4 }}>{r.title}</div>
          <div style={{ display:"flex", gap:7, flexWrap:"wrap", alignItems:"center" }}>
            <span style={{ fontSize:11, color:"var(--mut)", display:"flex", alignItems:"center", gap:3 }}><MapPin size={10}/>{r.city}</span>
            <span style={{ fontSize:10, color:"var(--mut)", textTransform:"capitalize" }}>{r.property_type.replace("_"," ")}</span>
            {r.surface>0&&<span style={{ fontSize:10, color:"var(--mut)" }}>{r.surface} m²</span>}
            <span style={{ fontSize:9, padding:"1px 5px", borderRadius:999, background:"var(--el)", color:"var(--mut)", border:"1px solid var(--bor)" }}>{r.source}</span>
          </div>
          {exp&&r.description&&<p style={{ fontSize:11, color:"var(--mut)", marginTop:8, lineHeight:1.5 }}>{r.description}</p>}
          {exp&&showFair&&r.surface>0&&<PriceFairness price={r.price} surface={r.surface} city={r.city} property_type={r.property_type}/>}
        </div>
        <div style={{ textAlign:"right", flexShrink:0 }}>
          <div style={{ fontFamily:"var(--font-display)", fontSize:16, fontWeight:600, color:"var(--gold)" }}>{(r.price/1000).toFixed(0)}K TND</div>
          <div style={{ fontSize:10, color:"var(--mut)", marginTop:1 }}>{r.price_per_m2.toLocaleString("fr-TN")} TND/m²</div>
          <div style={{ display:"flex", alignItems:"center", gap:4, marginTop:5, justifyContent:"flex-end" }}>
            <Shield size={9} color={c}/>
            <div style={{ width:28, height:3, background:"var(--el)", borderRadius:2, overflow:"hidden" }}><div style={{ height:"100%", width:`${r.trust_score*100}%`, background:c }}/></div>
            <span style={{ fontSize:10, color:c, fontWeight:600 }}>{r.trust_score.toFixed(2)}</span>
          </div>
        </div>
      </div>
      <div style={{ display:"flex", gap:5, marginTop:10, flexWrap:"wrap" }}>
        <button onClick={()=>setExp(e=>!e)} style={{ padding:"4px 9px", fontSize:11, borderRadius:6, border:"1px solid var(--bor)", background:"transparent", color:"var(--mut)", cursor:"pointer", fontFamily:"var(--font-body)" }}>{exp?"Moins":"Détails"}</button>
        {exp&&r.surface>0&&<button onClick={()=>setShowFair(s=>!s)} style={{ padding:"4px 9px", fontSize:11, borderRadius:6, border:"1px solid rgba(200,169,110,.3)", background:"rgba(200,169,110,.07)", color:"var(--gold)", cursor:"pointer", fontFamily:"var(--font-body)" }}>Prix juste ?</button>}
        <button onClick={()=>onAnalyze(r)} style={{ padding:"4px 9px", fontSize:11, borderRadius:6, border:"1px solid var(--gbor)", background:"var(--gdim)", color:"var(--gold)", cursor:"pointer", fontFamily:"var(--font-body)" }}>Analyser</button>
        {r.url&&<a href={r.url} target="_blank" rel="noopener noreferrer" style={{ display:"flex", alignItems:"center", gap:3, padding:"4px 9px", fontSize:11, borderRadius:6, border:"1px solid var(--bor)", color:"var(--mut)", textDecoration:"none" }}><ExternalLink size={9}/>Voir</a>}
        <button onClick={()=>saveFav(r)} style={{ padding:"4px 9px", fontSize:11, borderRadius:6, border:"1px solid var(--bor)", background:"transparent", color:"var(--mut)", cursor:"pointer", fontFamily:"var(--font-body)", marginLeft:"auto" }}>
          <Star size={9} style={{ marginRight:3 }}/>Sauvegarder
        </button>
      </div>
    </div>
  );
}

// ── Comparateur ────────────────────────────────────────────────────────────────
function Comparator({ items, onClose }: { items:Listing[]; onClose:()=>void }) {
  const bestPrice = Math.min(...items.map(i=>i.price));
  const bestTrust = Math.max(...items.map(i=>i.trust_score));
  const bestLegal = Math.min(...items.map(i=>i.legal_risk_score));
  const ROWS = [
    {label:"Ville",key:"city"as const},
    {label:"Type",key:"property_type"as const,fmt:(v:any)=>String(v).replace("_"," ")},
    {label:"Prix",key:"price"as const,fmt:(v:any)=>`${Number(v).toLocaleString("fr-TN")} TND`,clr:()=>"var(--gold)"},
    {label:"Surface",key:"surface"as const,fmt:(v:any)=>v>0?`${v} m²`:"—"},
    {label:"Prix/m²",key:"price_per_m2"as const,fmt:(v:any)=>`${Number(v).toLocaleString("fr-TN")} TND`},
    {label:"Trust score",key:"trust_score"as const,fmt:(v:any)=>Number(v).toFixed(3),clr:(v:any)=>TC(Number(v))},
    {label:"Risque légal",key:"legal_risk_score"as const,fmt:(v:any)=>Number(v).toFixed(3),clr:(v:any)=>LC(Number(v))},
    {label:"Source",key:"source"as const},
  ];
  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(0,0,0,.75)", display:"flex", alignItems:"center", justifyContent:"center", zIndex:1000, padding:20 }} onClick={onClose}>
      <div style={{ background:"var(--card)", border:"1px solid var(--bor)", borderRadius:14, width:"100%", maxWidth:900, maxHeight:"85vh", overflow:"auto" }} onClick={e=>e.stopPropagation()}>
        <div style={{ padding:"16px 20px", borderBottom:"1px solid var(--bor)", display:"flex", justifyContent:"space-between", alignItems:"center" }}>
          <div style={{ display:"flex", alignItems:"center", gap:8 }}>
            <GitCompare size={14} color="var(--gold)"/>
            <span style={{ fontFamily:"var(--font-display)", fontSize:15, fontWeight:600 }}>Comparateur</span>
            <span style={{ fontSize:11, color:"var(--mut)" }}>({items.length} biens)</span>
          </div>
          <button onClick={onClose} style={{ background:"none", border:"none", cursor:"pointer", color:"var(--mut)" }}><X size={15}/></button>
        </div>
        <div style={{ overflowX:"auto", padding:"0 4px 4px" }}>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
            <thead>
              <tr>
                <th style={{ padding:"10px 14px", textAlign:"left", fontSize:10, color:"var(--mut)", textTransform:"uppercase", background:"var(--el)", borderBottom:"1px solid var(--bor)", width:110 }}>Critère</th>
                {items.map(item=>(
                  <th key={item.id} style={{ padding:"10px 14px", textAlign:"left", background:"var(--el)", borderBottom:"1px solid var(--bor)", minWidth:170 }}>
                    <div style={{ fontSize:11, fontWeight:500, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis", maxWidth:170 }}>{item.title.slice(0,38)}...</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ROWS.map((row,ri)=>(
                <tr key={row.key} style={{ borderBottom:"1px solid var(--bor)", background:ri%2===0?"transparent":"rgba(255,255,255,.01)" }}>
                  <td style={{ padding:"9px 14px", color:"var(--mut)", fontSize:11, fontWeight:500 }}>{row.label}</td>
                  {items.map(item=>{
                    const raw = item[row.key];
                    const val = "fmt" in row&&row.fmt ? row.fmt(raw) : String(raw??"—");
                    const color = "clr" in row&&row.clr ? row.clr(raw) : "var(--txt)";
                    const isBest = (row.key==="price"&&item.price===bestPrice)||(row.key==="trust_score"&&item.trust_score===bestTrust)||(row.key==="legal_risk_score"&&item.legal_risk_score===bestLegal);
                    return (
                      <td key={item.id} style={{ padding:"9px 14px" }}>
                        <div style={{ display:"flex", alignItems:"center", gap:5 }}>
                          <span style={{ color, fontWeight:isBest?600:400 }}>{val}</span>
                          {isBest&&<span style={{ fontSize:9, padding:"1px 5px", borderRadius:999, background:"rgba(82,200,150,.15)", color:"#52C896", border:"1px solid rgba(82,200,150,.3)" }}>✓ Meilleur</span>}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
              {/* Ligne Prix Juste */}
              <tr style={{ borderBottom:"1px solid var(--bor)" }}>
                <td style={{ padding:"9px 14px", color:"var(--mut)", fontSize:11, fontWeight:500 }}>Évaluation prix</td>
                {items.map(item=>(
                  <td key={item.id} style={{ padding:"9px 14px" }}>
                    {item.surface>0?<PriceFairness price={item.price} surface={item.surface} city={item.city} property_type={item.property_type}/>:<span style={{ fontSize:11, color:"var(--mut)" }}>—</span>}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// PAGE
// ══════════════════════════════════════════════════════════════════════════════
export default function RecherchePage() {
  const [q,setPq]=useState(""); const [city,setCity]=useState(""); const [ptype,setPtype]=useState("");
  const [pmin,setPmin]=useState(""); const [pmax,setPmax]=useState(""); const [smin,setSmin]=useState("");
  const [tmin,setTmin]=useState("0"); const [sort,setSort]=useState("trust_score");
  const [showF,setShowF]=useState(false); const [results,setResults]=useState<Listing[]>(DEMO);
  const [loading,setLoading]=useState(false);
  const [analyzing,setAnalyzing]=useState<Listing|null>(null);
  const [aResult,setAResult]=useState<any>(null);
  const [selected,setSelected]=useState<number[]>([]);
  const [showCmp,setShowCmp]=useState(false);

  const search = useCallback(async()=>{
    setLoading(true);
    try {
      const p=new URLSearchParams();
      if(q) p.set("q",q); if(city) p.set("city",city); if(ptype) p.set("property_type",ptype);
      if(pmin) p.set("price_min",pmin); if(pmax) p.set("price_max",pmax); if(smin) p.set("surface_min",smin);
      if(tmin) p.set("trust_min",tmin); if(sort) p.set("sort_by",sort);
      const r=await fetch(`/api/search?${p}`);
      if(r.ok){const d=await r.json();setResults(d.results||[]);}
    } catch {
      let res=[...DEMO];
      if(q)    res=res.filter(r=>r.title.toLowerCase().includes(q.toLowerCase())||r.city.toLowerCase().includes(q.toLowerCase()));
      if(city) res=res.filter(r=>r.city.toLowerCase().includes(city.toLowerCase()));
      if(ptype)res=res.filter(r=>r.property_type===ptype);
      if(pmax) res=res.filter(r=>r.price<=Number(pmax));
      if(pmin) res=res.filter(r=>r.price>=Number(pmin));
      if(smin) res=res.filter(r=>r.surface>=Number(smin));
      if(tmin) res=res.filter(r=>r.trust_score>=Number(tmin));
      if(sort==="price_asc")  res.sort((a,b)=>a.price-b.price);
      if(sort==="price_desc") res.sort((a,b)=>b.price-a.price);
      if(sort==="trust_score")res.sort((a,b)=>b.trust_score-a.trust_score);
      if(sort==="ppm2_asc")   res.sort((a,b)=>a.price_per_m2-b.price_per_m2);
      setResults(res);
    }
    setLoading(false);
  },[q,city,ptype,pmin,pmax,smin,tmin,sort]);

  const analyze = async(r:Listing)=>{
    setAnalyzing(r);setAResult(null);
    try{const resp=await fetch("/api/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({description:r.description||r.title,price:r.price,surface:r.surface,city:r.city,property_type:r.property_type,source:r.source})});if(resp.ok)setAResult(await resp.json());}catch{}
  };

  const toggleSel=(id:number)=>setSelected(p=>p.includes(id)?p.filter(i=>i!==id):p.length<4?[...p,id]:p);
  const selItems=results.filter(r=>selected.includes(r.id));

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
      <div>
        <h1 style={{ fontFamily:"var(--font-display)", fontSize:22, fontWeight:600, marginBottom:4 }}>Recherche d'annonces</h1>
        <p style={{ fontSize:13, color:"var(--mut)" }}>{results.length} résultat(s) · cochez pour comparer · "Prix juste ?" dans Détails</p>
      </div>

      <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
        <div style={{ flex:1, minWidth:200, display:"flex", alignItems:"center", gap:10, background:"var(--card)", border:"1px solid var(--bor)", borderRadius:10, padding:"0 14px" }}>
          <Search size={14} color="var(--mut)"/>
          <input value={q} onChange={e=>setPq(e.target.value)} onKeyDown={e=>e.key==="Enter"&&search()} placeholder="Ville, type, mot-clé... (Entrée)" style={{ flex:1, background:"transparent", border:"none", outline:"none", color:"var(--txt)", fontSize:13, fontFamily:"var(--font-body)", padding:"11px 0" }}/>
          {q&&<button onClick={()=>setPq("")} style={{ background:"none", border:"none", cursor:"pointer", color:"var(--mut)" }}><X size={12}/></button>}
        </div>
        <button onClick={()=>setShowF(s=>!s)} style={{ display:"flex", alignItems:"center", gap:5, padding:"0 13px", borderRadius:10, border:`1px solid ${showF?"var(--gbor)":"var(--bor)"}`, background:showF?"var(--gdim)":"var(--card)", color:showF?"var(--gold)":"var(--mut)", cursor:"pointer", fontSize:12, fontFamily:"var(--font-body)" }}>
          <SlidersHorizontal size={12}/>Filtres
        </button>
        <button onClick={search} disabled={loading} style={{ padding:"0 18px", borderRadius:10, border:"none", background:"var(--gold)", color:"var(--card)", cursor:loading?"not-allowed":"pointer", fontSize:13, fontWeight:600, fontFamily:"var(--font-body)" }}>
          {loading?"...":"Rechercher"}
        </button>
        {selected.length>=2&&(
          <button onClick={()=>setShowCmp(true)} style={{ display:"flex", alignItems:"center", gap:5, padding:"0 14px", borderRadius:10, border:"1px solid var(--gbor)", background:"var(--gdim)", color:"var(--gold)", cursor:"pointer", fontSize:12, fontFamily:"var(--font-body)" }}>
            <GitCompare size={12}/>Comparer {selected.length}
          </button>
        )}
      </div>

      {showF&&(
        <div style={{ background:"var(--card)", border:"1px solid var(--bor)", borderRadius:10, padding:"14px 16px" }}>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:10, marginBottom:10 }}>
            {[{l:"Ville",el:<input value={city} onChange={e=>setCity(e.target.value)} placeholder="Ex: Sousse" style={IS}/>},
              {l:"Type",el:<select value={ptype} onChange={e=>setPtype(e.target.value)} style={IS}><option value="">Tous</option>{["appartement","villa","terrain","maison","studio","bureau_local"].map(t=><option key={t} value={t}>{t.replace("_"," ")}</option>)}</select>},
              {l:"Prix min",el:<input type="number" value={pmin} onChange={e=>setPmin(e.target.value)} placeholder="100000" style={IS}/>},
              {l:"Prix max",el:<input type="number" value={pmax} onChange={e=>setPmax(e.target.value)} placeholder="500000" style={IS}/>},
              {l:"Surface min",el:<input type="number" value={smin} onChange={e=>setSmin(e.target.value)} placeholder="80" style={IS}/>},
              {l:"Trust min",el:<select value={tmin} onChange={e=>setTmin(e.target.value)} style={IS}><option value="0">Tous</option><option value="0.5">≥ 0.50</option><option value="0.75">≥ 0.75</option></select>},
              {l:"Trier par",el:<select value={sort} onChange={e=>setSort(e.target.value)} style={IS}><option value="trust_score">Trust ↓</option><option value="price_asc">Prix ↑</option><option value="price_desc">Prix ↓</option><option value="ppm2_asc">Prix/m² ↑</option></select>},
            ].map(f=>(
              <div key={f.l}>
                <label style={{ fontSize:10, color:"var(--mut)", display:"block", marginBottom:4, textTransform:"uppercase", letterSpacing:".05em" }}>{f.l}</label>
                {f.el}
              </div>
            ))}
          </div>
          <div style={{ display:"flex", gap:8 }}>
            <button onClick={search} style={{ padding:"7px 15px", borderRadius:7, border:"none", background:"var(--gold)", color:"var(--card)", fontSize:12, fontWeight:600, cursor:"pointer", fontFamily:"var(--font-body)" }}>Appliquer</button>
            <button onClick={()=>{setPq("");setCity("");setPtype("");setPmin("");setPmax("");setSmin("");setTmin("0");setSort("trust_score");setResults(DEMO);}} style={{ padding:"7px 12px", borderRadius:7, border:"1px solid var(--bor)", background:"transparent", color:"var(--mut)", fontSize:12, cursor:"pointer", fontFamily:"var(--font-body)" }}>Reset</button>
          </div>
        </div>
      )}

      {selected.length===1&&<div style={{ fontSize:11, color:"var(--gold)", padding:"5px 10px", borderRadius:6, background:"rgba(200,169,110,.08)", border:"1px solid rgba(200,169,110,.2)" }}>Sélectionnez au moins 2 biens pour activer le comparateur.</div>}

      <div style={{ display:"grid", gridTemplateColumns:analyzing?"1fr 310px":"1fr", gap:14 }}>
        <div>
          {results.length===0?<div style={{ textAlign:"center", padding:"40px 0", color:"var(--mut)" }}>Aucun résultat.</div>
            :results.map(r=><Card key={r.id} r={r} selected={selected.includes(r.id)} onSelect={()=>toggleSel(r.id)} onAnalyze={analyze}/>)}
        </div>

        {analyzing&&(
          <div style={{ background:"var(--card)", border:"1px solid var(--bor)", borderRadius:10, padding:18, position:"sticky", top:72, alignSelf:"start" }}>
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:12 }}>
              <span style={{ fontSize:13, fontWeight:500 }}>Analyse IA</span>
              <button onClick={()=>{setAnalyzing(null);setAResult(null);}} style={{ background:"none", border:"none", cursor:"pointer", color:"var(--mut)" }}><X size={13}/></button>
            </div>
            <div style={{ fontSize:11, color:"var(--mut)", marginBottom:10 }}>{analyzing.title.slice(0,45)}...</div>
            {analyzing.surface>0&&<PriceFairness price={analyzing.price} surface={analyzing.surface} city={analyzing.city} property_type={analyzing.property_type}/>}
            {!aResult?(
              <div style={{ display:"flex", justifyContent:"center", padding:"16px 0" }}>
                <div style={{ width:20, height:20, border:"2px solid var(--gbor)", borderTop:"2px solid var(--gold)", borderRadius:"50%", animation:"spin 1s linear infinite" }}/>
              </div>
            ):(()=>{
              const vc={"FAVORABLE":"var(--ok)","ATTENTION":"var(--warn)","DANGER":"var(--bad)"}[aResult.verdict as string]||"var(--mut)";
              return (
                <div style={{ display:"flex", flexDirection:"column", gap:10, marginTop:10 }}>
                  <div style={{ background:`${vc}10`, border:`1px solid ${vc}28`, borderRadius:8, padding:"10px 12px" }}>
                    <div style={{ fontSize:14, fontWeight:600, color:vc }}>{aResult.verdict}</div>
                    <div style={{ fontSize:11, color:"var(--mut)", marginTop:3, lineHeight:1.5 }}>{aResult.recommendation}</div>
                  </div>
                  <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:8 }}>
                    <div style={{ background:"var(--el)", borderRadius:7, padding:"8px 10px" }}>
                      <div style={{ fontSize:9, color:"var(--mut)", marginBottom:2 }}>TRUST</div>
                      <div style={{ fontSize:16, fontWeight:600, color:TC(aResult.trust_score) }}>{aResult.trust_score.toFixed(3)}</div>
                    </div>
                    <div style={{ background:"var(--el)", borderRadius:7, padding:"8px 10px" }}>
                      <div style={{ fontSize:9, color:"var(--mut)", marginBottom:2 }}>LÉGAL</div>
                      <div style={{ fontSize:16, fontWeight:600, color:LC(aResult.legal_risk_score) }}>{aResult.legal_risk_score.toFixed(3)}</div>
                    </div>
                  </div>
                  {aResult.price_analysis&&<div style={{ fontSize:11, color:"var(--mut)", lineHeight:1.5 }}>{aResult.price_analysis}</div>}
                </div>
              );
            })()}
          </div>
        )}
      </div>

      {showCmp&&selItems.length>=2&&<Comparator items={selItems} onClose={()=>setShowCmp(false)}/>}
    </div>
  );
}
