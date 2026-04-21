"use client";
import { useState, useEffect, useCallback } from "react";
import {
  Clock, TrendingDown, TrendingUp, Home, DollarSign,
  Star, Calendar, RefreshCw, ExternalLink, ChevronDown, ChevronUp,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Cell, LineChart, Line, ReferenceLine
} from "recharts";

// ══════════════════════════════════════════════════════════════════════════════
// DONNÉES DÉMO
// ══════════════════════════════════════════════════════════════════════════════
const DEMO_DROPS = {
  drops:[
    {title:"Appartement S+3 La Marsa 120m²",city:"La Marsa",property_type:"appartement",surface:120,initial_price:335000,current_price:315000,drop_pct:5.9,drop_amount:20000,trust_score:0.84,url:"#"},
    {title:"Villa S+4 Hammamet Nord piscine",city:"Hammamet",property_type:"villa",surface:240,initial_price:570000,current_price:520000,drop_pct:8.7,drop_amount:50000,trust_score:0.77,url:"#"},
    {title:"Terrain 400m² Nabeul",city:"Nabeul",property_type:"terrain",surface:400,initial_price:112000,current_price:95000,drop_pct:15.2,drop_amount:17000,trust_score:0.31,url:"#"},
    {title:"Studio meublé Tunis centre",city:"Tunis",property_type:"studio",surface:52,initial_price:145000,current_price:130000,drop_pct:10.3,drop_amount:15000,trust_score:0.91,url:"#"},
    {title:"Appartement S+2 Sousse vue mer",city:"Sousse",property_type:"appartement",surface:95,initial_price:235000,current_price:215000,drop_pct:8.5,drop_amount:20000,trust_score:0.72,url:"#"},
  ],
  total:5, avg_drop_pct:9.7, max_drop_pct:15.2,
};
const DEMO_YIELD = {
  results:[
    {city:"Sfax",property_type:"appartement",median_rent:550,median_sale_price:160000,yield_brut_pct:4.13,yield_net_pct:3.09,verdict:"correct"},
    {city:"Sousse",property_type:"appartement",median_rent:750,median_sale_price:215000,yield_brut_pct:4.19,yield_net_pct:3.14,verdict:"correct"},
    {city:"Monastir",property_type:"appartement",median_rent:650,median_sale_price:200000,yield_brut_pct:3.90,yield_net_pct:2.93,verdict:"correct"},
    {city:"Nabeul",property_type:"appartement",median_rent:600,median_sale_price:190000,yield_brut_pct:3.79,yield_net_pct:2.84,verdict:"correct"},
    {city:"Tunis",property_type:"appartement",median_rent:900,median_sale_price:250000,yield_brut_pct:4.32,yield_net_pct:3.24,verdict:"correct"},
    {city:"Hammamet",property_type:"villa",median_rent:1800,median_sale_price:520000,yield_brut_pct:4.15,yield_net_pct:3.11,verdict:"correct"},
    {city:"Bizerte",property_type:"appartement",median_rent:500,median_sale_price:175000,yield_brut_pct:3.43,yield_net_pct:2.57,verdict:"faible"},
    {city:"La Marsa",property_type:"appartement",median_rent:950,median_sale_price:310000,yield_brut_pct:3.68,yield_net_pct:2.76,verdict:"faible"},
  ],
  best_city:"Tunis", avg_yield:3.95,
};
const DEMO_NEGO = [
  {title:"Appartement S+3 La Marsa",city:"La Marsa",price:315000,days_on_market:87,negociation_score:0.72,seller_type:"particulier",estimated_reduction_pct:10.8,trust_score:0.84,url:"#"},
  {title:"Villa S+4 Hammamet",city:"Hammamet",price:520000,days_on_market:134,negociation_score:0.88,seller_type:"particulier",estimated_reduction_pct:13.2,trust_score:0.77,url:"#"},
  {title:"Terrain Nabeul 400m²",city:"Nabeul",price:95000,days_on_market:212,negociation_score:0.94,seller_type:"agence_informelle",estimated_reduction_pct:14.1,trust_score:0.31,url:"#"},
  {title:"Maison Bizerte R+1",city:"Bizerte",price:195000,days_on_market:95,negociation_score:0.68,seller_type:"particulier",estimated_reduction_pct:10.2,trust_score:0.69,url:"#"},
  {title:"Local commercial Sfax",city:"Sfax",price:320000,days_on_market:156,negociation_score:0.82,seller_type:"revendeur_actif",estimated_reduction_pct:12.3,trust_score:0.61,url:"#"},
];
const DEMO_WINDOW = {
  monthly_index:[
    {month:1,month_name:"Janvier",delta_vs_avg:-4.2,verdict:"favorable"},
    {month:2,month_name:"Février",delta_vs_avg:-3.8,verdict:"favorable"},
    {month:3,month_name:"Mars",delta_vs_avg:-1.5,verdict:"neutre"},
    {month:4,month_name:"Avril",delta_vs_avg:1.2,verdict:"neutre"},
    {month:5,month_name:"Mai",delta_vs_avg:3.5,verdict:"défavorable"},
    {month:6,month_name:"Juin",delta_vs_avg:5.1,verdict:"défavorable"},
    {month:7,month_name:"Juillet",delta_vs_avg:6.8,verdict:"défavorable"},
    {month:8,month_name:"Août",delta_vs_avg:4.2,verdict:"défavorable"},
    {month:9,month_name:"Septembre",delta_vs_avg:2.1,verdict:"neutre"},
    {month:10,month_name:"Octobre",delta_vs_avg:0.5,verdict:"neutre"},
    {month:11,month_name:"Novembre",delta_vs_avg:-2.3,verdict:"favorable"},
    {month:12,month_name:"Décembre",delta_vs_avg:-5.5,verdict:"favorable"},
  ],
  current_month:"Avril", current_verdict:"neutre", current_delta_pct:1.2,
  recommendation:"Période neutre (+1.2% vs moyenne). Les mois les plus favorables sont Décembre, Janvier, Février.",
};

// ── Helpers ────────────────────────────────────────────────────────────────
const TC  = (s:number) => s>=.75?"#52C896":s>=.5?"#E8A84C":"#E05C5C";
const YC  = (y:number) => y>=7?"#52C896":y>=5?"#C8A96E":y>=3?"#E8A84C":"#E05C5C";
const NS  = (n:number) => n>=.80?"#52C896":n>=.60?"#E8A84C":"var(--mut)";
const BAR_C=(d:number) => d<-2?"#52C896":d>2?"#E05C5C":"#6B9FE8";

const STYPE_LABEL:Record<string,string> = {
  agence_pro:"Agence pro",agence_informelle:"Agence info.",
  revendeur_actif:"Revendeur actif",particulier:"Particulier",
};

// ══════════════════════════════════════════════════════════════════════════════
// PAGE
// ══════════════════════════════════════════════════════════════════════════════
export default function OpportunitesPage() {
  const [drops,  setDrops]  = useState<any>(DEMO_DROPS);
  const [yield_, setYield]  = useState<any>(DEMO_YIELD);
  const [nego,   setNego]   = useState<any[]>(DEMO_NEGO);
  const [window_,setWindow] = useState<any>(DEMO_WINDOW);
  const [loading,setLoading]= useState(false);
  const [tab,    setTab]    = useState<"drops"|"yield"|"nego"|"window">("drops");
  const [expRow, setExpRow] = useState<number|null>(null);
  const [calcP,  setCalcP]  = useState("");
  const [calcC,  setCalcC]  = useState("Sousse");
  const [calcT,  setCalcT]  = useState("appartement");
  const [calcRes,setCalcRes]= useState<any>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [rd,ry,rs,rw] = await Promise.all([
        fetch("/api/price-drops").then(r=>r.ok?r.json():null),
        fetch("/api/rental-yield").then(r=>r.ok?r.json():null),
        fetch("/api/seller-score?top_n=20").then(r=>r.ok?r.json():null),
        fetch("/api/buying-window").then(r=>r.ok?r.json():null),
      ]);
      if(rd) setDrops(rd);
      if(ry) setYield(ry);
      if(rs?.top_negotiable) setNego(rs.top_negotiable);
      if(rw) setWindow(rw);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(()=>{ load(); },[]);

  const calcYield = async () => {
    if (!calcP) return;
    try {
      const r = await fetch(`/api/rental-yield/calculator?price=${calcP}&city=${encodeURIComponent(calcC)}&property_type=${calcT}`);
      if (r.ok) setCalcRes(await r.json());
    } catch {
      const loyer = 700;
      const yb = round2(Number(calcP)>0 ? loyer*12/Number(calcP)*100 : 0);
      setCalcRes({price:Number(calcP),city:calcC,estimated_monthly_rent:loyer,yield_brut_pct:yb,yield_net_pct:round2(yb*.75),annual_rent:loyer*12,verdict:yb>=5?"bon":"correct"});
    }
  };

  const round2 = (n:number) => Math.round(n*100)/100;

  const IS = {padding:"7px 10px",borderRadius:7,fontSize:12,border:"1px solid var(--bor)",background:"var(--el)",color:"var(--txt)",fontFamily:"var(--font-body)",width:"100%"} as const;

  const TABS = [
    {id:"drops",  label:"💰 Prix baissés",       count:drops?.total||0,       color:"#52C896"},
    {id:"yield",  label:"🏢 Rendement locatif",  count:yield_?.results?.length||0, color:"#C8A96E"},
    {id:"nego",   label:"🤝 Négociables",         count:nego?.length||0,       color:"#E8A84C"},
    {id:"window", label:"📅 Fenêtre d'achat",    count:null,                   color:"#6B9FE8"},
  ] as const;

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:20 }}>
      {/* Header */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start" }}>
        <div>
          <h1 style={{ fontFamily:"var(--font-display)", fontSize:22, fontWeight:600, marginBottom:4 }}>
            Opportunités du marché
          </h1>
          <p style={{ fontSize:13, color:"var(--mut)" }}>
            5 outils introuvables ailleurs en Tunisie — pour acheter au bon prix, au bon moment
          </p>
        </div>
        <button onClick={load} disabled={loading} style={{ display:"flex", alignItems:"center", gap:5, padding:"6px 13px", borderRadius:8, border:"1px solid var(--bor)", background:"transparent", color:"var(--mut)", fontSize:12, cursor:loading?"not-allowed":"pointer", fontFamily:"var(--font-body)" }}>
          <RefreshCw size={11} style={{ animation:loading?"spin 1s linear infinite":"none" }}/>
          {loading?"...":"Actualiser"}
        </button>
      </div>

      {/* KPIs globaux */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12 }}>
        {[
          {label:"Baisses détectées", val:drops?.total||0,        color:"#52C896",  sub:`Moy. −${drops?.avg_drop_pct||0}%`},
          {label:"Meilleur rendement",val:`${yield_?.results?.[0]?.yield_brut_pct||0}%`,color:"#C8A96E",sub:yield_?.results?.[0]?.city||"—"},
          {label:"Top négociation",   val:`${Math.round((nego?.[0]?.negociation_score||0)*100)}%`,color:"#E8A84C",sub:nego?.[0]?.city||"—"},
          {label:"Fenêtre actuelle",  val:window_?.current_verdict==="favorable"?"✅ Favorable":window_?.current_verdict==="défavorable"?"⛔ Attendre":"⬜ Neutre",color:window_?.current_verdict==="favorable"?"#52C896":window_?.current_verdict==="défavorable"?"#E05C5C":"#6B9FE8",sub:`${window_?.current_delta_pct>0?"+":""}${window_?.current_delta_pct||0}% vs moy.`},
        ].map(k=>(
          <div key={k.label} style={{ background:"var(--card)", border:"1px solid var(--bor)", borderRadius:12, padding:"16px 18px" }}>
            <div style={{ fontFamily:"var(--font-display)", fontSize:22, fontWeight:600, color:k.color }}>{k.val}</div>
            <div style={{ fontSize:11, color:"var(--mut)", marginTop:2 }}>{k.label}</div>
            <div style={{ fontSize:10, color:k.color, marginTop:2 }}>{k.sub}</div>
          </div>
        ))}
      </div>

      {/* Onglets */}
      <div style={{ display:"flex", gap:4, background:"var(--el)", padding:4, borderRadius:10, border:"1px solid var(--bor)" }}>
        {TABS.map(t=>(
          <button key={t.id} onClick={()=>setTab(t.id)} style={{ flex:1, padding:"8px 4px", borderRadius:7, border:"none", cursor:"pointer", fontSize:12, fontFamily:"var(--font-body)", background:tab===t.id?"var(--card)":"transparent", color:tab===t.id?t.color:"var(--mut)", fontWeight:tab===t.id?500:400, display:"flex", alignItems:"center", justifyContent:"center", gap:5 }}>
            {t.label}{t.count!==null&&<span style={{ fontSize:10, padding:"1px 5px", borderRadius:999, background:tab===t.id?`${t.color}14`:"transparent", color:t.color }}>{t.count}</span>}
          </button>
        ))}
      </div>

      {/* ── TAB 1 : Prix baissés ──────────────────────────────────────────── */}
      {tab==="drops"&&(
        <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
          <div style={{ fontSize:11, color:"var(--mut)" }}>
            💡 Ces biens ont baissé de prix depuis leur première mise en ligne. Une baisse = vendeur sous pression = pouvoir de négociation.
          </div>
          {drops?.drops?.map((d:any,i:number)=>(
            <div key={i} style={{ background:"var(--card)", border:"1px solid rgba(82,200,150,.25)", borderRadius:10, padding:"14px 16px" }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", gap:10 }}>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ fontSize:13, fontWeight:500, marginBottom:4, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{d.title}</div>
                  <div style={{ fontSize:11, color:"var(--mut)" }}>{d.city} · {d.property_type}{d.surface>0?` · ${d.surface}m²`:""}</div>
                </div>
                <div style={{ textAlign:"right", flexShrink:0 }}>
                  <div style={{ fontSize:14, fontWeight:700, color:"#52C896", fontFamily:"var(--font-display)" }}>
                    −{d.drop_pct}%
                  </div>
                  <div style={{ fontSize:10, color:"var(--mut)" }}>−{d.drop_amount.toLocaleString("fr-TN")} TND</div>
                </div>
              </div>
              <div style={{ display:"flex", gap:12, marginTop:10, flexWrap:"wrap", alignItems:"center" }}>
                <div style={{ fontSize:11, color:"var(--mut)" }}>
                  Avant : <s style={{ color:"var(--mut)" }}>{d.initial_price.toLocaleString("fr-TN")} TND</s>
                </div>
                <span style={{ color:"var(--mut)" }}>→</span>
                <div style={{ fontSize:13, fontWeight:600, color:"var(--gold)", fontFamily:"var(--font-display)" }}>
                  {d.current_price.toLocaleString("fr-TN")} TND
                </div>
                <span style={{ fontSize:10, padding:"2px 7px", borderRadius:999, background:`${TC(d.trust_score)}12`, color:TC(d.trust_score), border:`1px solid ${TC(d.trust_score)}22` }}>
                  Trust {d.trust_score.toFixed(2)}
                </span>
                {d.url&&d.url!=="#"&&<a href={d.url} target="_blank" rel="noopener noreferrer" style={{ marginLeft:"auto", display:"flex", alignItems:"center", gap:3, fontSize:11, color:"var(--mut)", textDecoration:"none" }}><ExternalLink size={10}/>Voir</a>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── TAB 2 : Rendement locatif ─────────────────────────────────────── */}
      {tab==="yield"&&(
        <div style={{ display:"grid", gridTemplateColumns:"1fr 340px", gap:16, alignItems:"start" }}>
          <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
            <div style={{ fontSize:11, color:"var(--mut)" }}>
              💡 Rendement brut = (loyer mensuel médian × 12) ÷ prix de vente médian. Le rendement net est estimé à 75% (après charges, vacance, fiscalité tunisienne).
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={yield_?.results?.slice(0,8)||[]} layout="vertical">
                <XAxis type="number" tick={{fontSize:10,fill:"var(--mut)"}} axisLine={false} tickLine={false} tickFormatter={v=>`${v}%`}/>
                <YAxis dataKey="city" type="category" tick={{fontSize:11,fill:"var(--txt)"}} axisLine={false} tickLine={false} width={80}/>
                <Tooltip contentStyle={{background:"var(--el)",border:"1px solid var(--bor)",borderRadius:8,fontSize:11}} formatter={(v:number)=>[`${v}%`,"Rendement brut"]}/>
                <Bar dataKey="yield_brut_pct" radius={[0,4,4,0]}>
                  {(yield_?.results?.slice(0,8)||[]).map((r:any,i:number)=>(
                    <Cell key={i} fill={YC(r.yield_brut_pct)}/>
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            {(yield_?.results||[]).map((r:any,i:number)=>(
              <div key={i} style={{ background:"var(--card)", border:"1px solid var(--bor)", borderRadius:10, padding:"12px 16px", display:"flex", justifyContent:"space-between", alignItems:"center" }}>
                <div>
                  <div style={{ fontSize:13, fontWeight:500 }}>{r.city} · <span style={{ textTransform:"capitalize",color:"var(--mut)" }}>{r.property_type}</span></div>
                  <div style={{ fontSize:11, color:"var(--mut)", marginTop:3 }}>
                    Loyer méd. {r.median_rent.toLocaleString("fr-TN")} TND/mois · Prix méd. {(r.median_sale_price/1000).toFixed(0)}K TND
                  </div>
                </div>
                <div style={{ textAlign:"right" }}>
                  <div style={{ fontFamily:"var(--font-display)", fontSize:20, fontWeight:700, color:YC(r.yield_brut_pct) }}>{r.yield_brut_pct}%</div>
                  <div style={{ fontSize:10, color:"var(--mut)" }}>brut · net {r.yield_net_pct}%</div>
                  <span style={{ fontSize:10, padding:"2px 7px", borderRadius:999, background:`${YC(r.yield_brut_pct)}14`, color:YC(r.yield_brut_pct) }}>{r.verdict}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Calculateur */}
          <div style={{ background:"var(--card)", border:"1px solid var(--bor)", borderRadius:12, padding:20, position:"sticky", top:72 }}>
            <div style={{ fontSize:14, fontWeight:600, marginBottom:14, color:"var(--gold)" }}>🧮 Calculateur rendement</div>
            <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
              {[
                {l:"Prix d'achat (TND)", el:<input type="number" value={calcP} onChange={e=>setCalcP(e.target.value)} placeholder="Ex: 215000" style={IS}/>},
                {l:"Ville", el:<input value={calcC} onChange={e=>setCalcC(e.target.value)} placeholder="Ex: Sousse" style={IS}/>},
                {l:"Type de bien", el:<select value={calcT} onChange={e=>setCalcT(e.target.value)} style={IS}><option value="appartement">Appartement</option><option value="villa">Villa</option><option value="studio">Studio</option></select>},
              ].map(f=>(
                <div key={f.l}>
                  <label style={{ fontSize:10, color:"var(--mut)", display:"block", marginBottom:4, textTransform:"uppercase", letterSpacing:".05em" }}>{f.l}</label>
                  {f.el}
                </div>
              ))}
              <button onClick={calcYield} style={{ padding:"9px 0", borderRadius:8, border:"none", background:"var(--gold)", color:"var(--card)", fontSize:13, fontWeight:600, cursor:"pointer", fontFamily:"var(--font-body)" }}>
                Calculer le rendement
              </button>
            </div>
            {calcRes&&!calcRes.error&&(
              <div style={{ marginTop:14, background:`${YC(calcRes.yield_brut_pct)}08`, border:`1px solid ${YC(calcRes.yield_brut_pct)}25`, borderRadius:10, padding:"14px 16px" }}>
                <div style={{ fontFamily:"var(--font-display)", fontSize:28, fontWeight:700, color:YC(calcRes.yield_brut_pct) }}>{calcRes.yield_brut_pct}%</div>
                <div style={{ fontSize:11, color:"var(--mut)", marginBottom:10 }}>rendement brut annuel</div>
                {[
                  {l:"Loyer mensuel estimé",v:`${calcRes.estimated_monthly_rent?.toLocaleString("fr-TN")} TND`},
                  {l:"Revenus annuels",      v:`${calcRes.annual_rent?.toLocaleString("fr-TN")} TND`},
                  {l:"Rendement net estimé", v:`${calcRes.yield_net_pct}%`},
                  {l:"Verdict",              v:calcRes.verdict},
                ].map(r=>(
                  <div key={r.l} style={{ display:"flex", justifyContent:"space-between", fontSize:12, padding:"4px 0", borderBottom:"1px solid var(--bor)" }}>
                    <span style={{ color:"var(--mut)" }}>{r.l}</span>
                    <b style={{ color:"var(--txt)" }}>{r.v}</b>
                  </div>
                ))}
                <p style={{ fontSize:10, color:"var(--mut)", marginTop:8, lineHeight:1.5 }}>
                  Rendement net estimé à 75% du brut (charges, vacance ~2 mois/an, fiscalité tunisienne).
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── TAB 3 : Top négociables ───────────────────────────────────────── */}
      {tab==="nego"&&(
        <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
          <div style={{ fontSize:11, color:"var(--mut)" }}>
            💡 Score calculé sur : jours sur le marché, mentions "prix négociable" dans la description, nombre d'annonces du vendeur. Plus le score est élevé, plus la négociation est probable.
          </div>
          {nego?.map((r:any,i:number)=>(
            <div key={i} style={{ background:"var(--card)", border:`1px solid ${NS(r.negociation_score)}22`, borderRadius:10, padding:"14px 16px" }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", gap:10 }}>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ fontSize:13, fontWeight:500, marginBottom:4, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{r.title}</div>
                  <div style={{ display:"flex", gap:8, flexWrap:"wrap", alignItems:"center" }}>
                    <span style={{ fontSize:11, color:"var(--mut)" }}>{r.city}</span>
                    <span style={{ fontSize:10, padding:"1px 6px", borderRadius:999, background:"var(--el)", color:"var(--mut)", border:"1px solid var(--bor)" }}>
                      {STYPE_LABEL[r.seller_type]||r.seller_type}
                    </span>
                    <span style={{ fontSize:10, color:"var(--mut)", display:"flex", alignItems:"center", gap:3 }}>
                      <Clock size={10}/>{r.days_on_market}j en ligne
                    </span>
                  </div>
                </div>
                <div style={{ textAlign:"right", flexShrink:0 }}>
                  <div style={{ fontFamily:"var(--font-display)", fontSize:16, fontWeight:600, color:"var(--gold)" }}>{(r.price/1000).toFixed(0)}K TND</div>
                  <div style={{ fontSize:11, fontWeight:600, color:NS(r.negociation_score) }}>
                    Score négo : {Math.round(r.negociation_score*100)}%
                  </div>
                  <div style={{ fontSize:10, color:"#52C896" }}>
                    Réduction estimée ~{r.estimated_reduction_pct}%
                  </div>
                </div>
              </div>
              <div style={{ marginTop:10 }}>
                <div style={{ height:4, background:"var(--el)", borderRadius:2, overflow:"hidden" }}>
                  <div style={{ height:"100%", width:`${r.negociation_score*100}%`, background:NS(r.negociation_score), borderRadius:2 }}/>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── TAB 4 : Fenêtre d'achat ──────────────────────────────────────── */}
      {tab==="window"&&(
        <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
          {/* Verdict actuel */}
          {(()=>{
            const vc = window_?.current_verdict==="favorable"?"#52C896":window_?.current_verdict==="défavorable"?"#E05C5C":"#6B9FE8";
            return (
              <div style={{ background:`${vc}08`, border:`1px solid ${vc}25`, borderRadius:12, padding:"16px 20px" }}>
                <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:8 }}>
                  <Calendar size={16} color={vc}/>
                  <span style={{ fontSize:14, fontWeight:600, color:vc }}>
                    {window_?.current_month} — {window_?.current_verdict==="favorable"?"Bon moment pour acheter":window_?.current_verdict==="défavorable"?"Période de prix élevés":"Période neutre"}
                  </span>
                  <span style={{ fontSize:13, fontWeight:700, color:vc, marginLeft:"auto" }}>
                    {window_?.current_delta_pct>0?"+":""}{window_?.current_delta_pct}%
                  </span>
                </div>
                <p style={{ fontSize:12, color:"var(--txt)", lineHeight:1.6, margin:0 }}>{window_?.recommendation}</p>
              </div>
            );
          })()}

          {/* Graphique saisonnalité */}
          <div style={{ background:"var(--card)", border:"1px solid var(--bor)", borderRadius:12, padding:22 }}>
            <div style={{ fontSize:13, fontWeight:600, marginBottom:6 }}>Indice saisonnier des prix</div>
            <div style={{ fontSize:11, color:"var(--mut)", marginBottom:14 }}>
              Valeur = écart % au prix annuel moyen. Négatif = prix plus bas que la moyenne = opportunité.
            </div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={window_?.monthly_index||[]}>
                <XAxis dataKey="month_name" tick={{fontSize:9,fill:"var(--mut)"}} axisLine={false} tickLine={false}
                  tickFormatter={s=>s.slice(0,3)}/>
                <YAxis tick={{fontSize:10,fill:"var(--mut)"}} axisLine={false} tickLine={false}
                  tickFormatter={v=>`${v>0?"+":""}${v}%`}/>
                <Tooltip contentStyle={{background:"var(--el)",border:"1px solid var(--bor)",borderRadius:8,fontSize:11}}
                  formatter={(v:number)=>[`${v>0?"+":""}${v}%`,"Écart vs moyenne"]}/>
                <ReferenceLine y={0} stroke="var(--mut)" strokeDasharray="3 3"/>
                <Bar dataKey="delta_vs_avg" radius={[3,3,0,0]}>
                  {(window_?.monthly_index||[]).map((m:any,i:number)=>(
                    <Cell key={i} fill={BAR_C(m.delta_vs_avg)}/>
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div style={{ display:"flex", gap:16, marginTop:10, fontSize:10, color:"var(--mut)" }}>
              <span><span style={{ color:"#52C896" }}>■</span> Favorable (prix bas)</span>
              <span><span style={{ color:"#6B9FE8" }}>■</span> Neutre</span>
              <span><span style={{ color:"#E05C5C" }}>■</span> Défavorable (prix hauts)</span>
            </div>
          </div>

          {/* Note méthodologique */}
          {window_?.warning&&(
            <div style={{ fontSize:11, color:"var(--mut)", padding:"8px 12px", borderRadius:7, background:"var(--el)", border:"1px solid var(--bor)" }}>
              ⚠️ {window_?.warning}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
