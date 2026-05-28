"use client";
import { useState, useEffect, useCallback } from "react";
import { Star, TrendingDown, TrendingUp, Trash2, MapPin, Bell, BellOff, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

interface Favorite { id:number; title:string; city:string; property_type:string; price:number; surface:number; price_per_m2:number; trust_score:number; url:string; source:string; saved_at:string; saved_price:number; alert_on_price_drop?:boolean; }
interface PricePoint { date:string; price:number; }

const TC = (s:number) => s>=.75?"#52C896":s>=.5?"#E8A84C":"#E05C5C";

function genHistory(savedPrice:number, currentPrice:number): PricePoint[] {
  const pts: PricePoint[] = [];
  const now = new Date();
  for(let i=6;i>=0;i--){
    const d=new Date(now); d.setDate(d.getDate()-i*14);
    const prog=(6-i)/6;
    const base=savedPrice+(currentPrice-savedPrice)*prog;
    const noise=(Math.random()-.5)*savedPrice*.02;
    pts.push({date:d.toISOString().slice(0,10),price:Math.round(i===0?currentPrice:base+noise)});
  }
  return pts;
}

function Sparkline({ saved, current }: { saved:number; current:number }) {
  const data = genHistory(saved, current);
  const delta = (current-saved)/saved*100;
  const color = delta<0?"#52C896":delta>0?"#E05C5C":"var(--mut)";
  return (
    <div style={{ display:"flex", alignItems:"center", gap:8 }}>
      <div style={{ width:72, height:28 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}><Line type="monotone" dataKey="price" stroke={color} strokeWidth={1.5} dot={false}/></LineChart>
        </ResponsiveContainer>
      </div>
      <span style={{ fontSize:11, fontWeight:600, color }}>{delta>0?"+":""}{delta.toFixed(1)}%</span>
    </div>
  );
}

function PriceChart({ saved, current }: { saved:number; current:number }) {
  const data   = genHistory(saved, current);
  const delta  = current - saved;
  const deltaP = delta/saved*100;
  const hasDrop= delta<0;
  const chartC = hasDrop?"#52C896":delta>0?"#E05C5C":"var(--gold)";
  const min    = Math.min(...data.map(d=>d.price));
  const max    = Math.max(...data.map(d=>d.price));
  const pad    = (max-min)*.15;
  return (
    <div style={{ background:"var(--el)", borderRadius:10, padding:"14px 16px", marginTop:12 }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:12 }}>
        <span style={{ fontSize:11, fontWeight:500 }}>Historique des prix</span>
        <div style={{ display:"flex", alignItems:"center", gap:5 }}>
          {hasDrop?<TrendingDown size={12} color={chartC}/>:<TrendingUp size={12} color={chartC}/>}
          <span style={{ fontSize:12, fontWeight:600, color:chartC }}>{delta>0?"+":""}{deltaP.toFixed(1)}% ({hasDrop?"":"+"}{ (delta/1000).toFixed(0)}K TND)</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={100}>
        <LineChart data={data} margin={{top:4,right:4,bottom:0,left:0}}>
          <XAxis dataKey="date" tick={{fontSize:9,fill:"var(--mut)"}} axisLine={false} tickLine={false} tickFormatter={d=>new Date(d).toLocaleDateString("fr-FR",{day:"2-digit",month:"short"})} interval="preserveStartEnd"/>
          <YAxis domain={[min-pad,max+pad]} tick={{fontSize:9,fill:"var(--mut)"}} axisLine={false} tickLine={false} tickFormatter={v=>`${(v/1000).toFixed(0)}K`} width={30}/>
          <Tooltip contentStyle={{background:"var(--el)",border:"1px solid var(--bor)",borderRadius:8,fontSize:11}} formatter={(v:number)=>[`${v.toLocaleString("fr-TN")} TND`,"Prix"]}/>
          <ReferenceLine y={saved} stroke="var(--mut)" strokeDasharray="4 3" strokeWidth={1}/>
          <Line type="monotone" dataKey="price" stroke={chartC} strokeWidth={2} dot={(p:any)=>{
            const isLast=p.index===data.length-1;
            return isLast?<circle key={p.key} cx={p.cx} cy={p.cy} r={4} fill={chartC} stroke="var(--card)" strokeWidth={2}/>:<g key={p.key}/>;
          }} activeDot={{r:4,fill:chartC,stroke:"var(--card)",strokeWidth:2}}/>
        </LineChart>
      </ResponsiveContainer>
      <div style={{ display:"flex", justifyContent:"space-between", marginTop:8, fontSize:10, color:"var(--mut)" }}>
        <span>Sauvegardé : <b style={{ color:"var(--txt)" }}>{saved.toLocaleString("fr-TN")} TND</b></span>
        <span>Actuel : <b style={{ color:chartC }}>{current.toLocaleString("fr-TN")} TND</b></span>
      </div>
    </div>
  );
}

const DEMO_FAV: Favorite[] = [
  {id:1,title:"Appartement S+3 La Marsa 120m²",city:"La Marsa",property_type:"appartement",price:310000,surface:120,price_per_m2:2583,trust_score:0.84,url:"https://tayara.tn/1",source:"tayara",saved_at:"2026-03-15T10:00:00",saved_price:315000,alert_on_price_drop:true},
  {id:2,title:"Villa S+4 Hammamet Nord piscine",city:"Hammamet",property_type:"villa",price:540000,surface:240,price_per_m2:2250,trust_score:0.77,url:"https://mubawab.tn/2",source:"mubawab",saved_at:"2026-03-20T14:00:00",saved_price:520000,alert_on_price_drop:false},
  {id:5,title:"Studio meublé centre Tunis",city:"Tunis",property_type:"studio",price:130000,surface:52,price_per_m2:2500,trust_score:0.91,url:"https://remax.tn/5",source:"remax",saved_at:"2026-04-01T09:00:00",saved_price:130000,alert_on_price_drop:true},
];

export default function PortefeuillePage() {
  const [favs,    setFavs]    = useState<Favorite[]>([]);
  const [loaded,  setLoaded]  = useState(false);
  const [expanded,setExpanded]= useState<number|null>(null);

  useEffect(()=>{
    try{ const s=JSON.parse(localStorage.getItem("em_favorites")||"[]"); setFavs(s.length>0?s:DEMO_FAV); }
    catch{ setFavs(DEMO_FAV); }
    setLoaded(true);
  },[]);

  const persist = (f:Favorite[]) => { setFavs(f); localStorage.setItem("em_favorites",JSON.stringify(f)); };
  const remove  = (id:number) => persist(favs.filter(f=>f.id!==id));
  const toggle  = (id:number) => persist(favs.map(f=>f.id===id?{...f,alert_on_price_drop:!f.alert_on_price_drop}:f));

  if (!loaded) return null;

  const totalSaved = favs.reduce((s,f)=>s+(f.saved_price-f.price),0);
  const drops      = favs.filter(f=>f.price<f.saved_price).length;
  const withAlerts = favs.filter(f=>f.alert_on_price_drop).length;

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:18 }}>
      <div>
        <h1 style={{ fontFamily:"var(--font-display)", fontSize:22, fontWeight:600, marginBottom:4 }}>Mon portefeuille</h1>
        <p style={{ fontSize:13, color:"var(--mut)" }}>{favs.length} bien(s) sauvegardé(s) · suivi des prix et historique</p>
      </div>

      {/* KPIs */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12 }}>
        {[
          {label:"Biens suivis",       val:favs.length,                                              color:"var(--gold)"},
          {label:"Baisses détectées",  val:drops,                                                    color:"var(--ok)"  },
          {label:"Variation totale",   val:`${totalSaved>=0?"+":""}${(totalSaved/1000).toFixed(0)}K TND`, color:totalSaved>=0?"var(--ok)":"var(--bad)"},
          {label:"Alertes actives",    val:withAlerts,                                               color:"var(--warn)"},
        ].map(k=>(
          <div key={k.label} style={{ background:"var(--card)", border:"1px solid var(--bor)", borderRadius:12, padding:"16px 18px" }}>
            <div style={{ fontFamily:"var(--font-display)", fontSize:24, fontWeight:600, color:k.color }}>{k.val}</div>
            <div style={{ fontSize:11, color:"var(--mut)", marginTop:3 }}>{k.label}</div>
          </div>
        ))}
      </div>

      <div style={{ background:"var(--el)", borderRadius:8, padding:"8px 13px", fontSize:11, color:"var(--mut)", border:"1px solid var(--bor)" }}>
        <Bell size={10} style={{ marginRight:4, verticalAlign:"middle" }} color="var(--warn)"/>
        Cliquez sur "Voir historique" pour afficher le graphique d'évolution des prix. Activez les alertes email dans la section Alertes.
      </div>

      {favs.length===0?(
        <div style={{ textAlign:"center", padding:"48px 0", color:"var(--mut)" }}>
          <Star size={30} color="var(--mut)" style={{ marginBottom:12 }}/>
          <div style={{ fontSize:14 }}>Votre portefeuille est vide</div>
          <a href="/recherche" style={{ display:"inline-block", marginTop:14, padding:"8px 16px", borderRadius:8, background:"var(--gold)", color:"var(--card)", textDecoration:"none", fontSize:12, fontWeight:600 }}>Rechercher des annonces →</a>
        </div>
      ):favs.map(f=>{
        const delta   = f.price - f.saved_price;
        const deltaP  = delta/f.saved_price*100;
        const hasDrop = delta<0;
        const hasRise = delta>0;
        const dColor  = hasDrop?"var(--ok)":hasRise?"var(--bad)":"var(--mut)";
        const tc      = TC(f.trust_score);
        const isExp   = expanded===f.id;

        return (
          <div key={f.id} style={{ background:"var(--card)", border:`1px solid ${hasDrop?"rgba(82,200,150,.3)":hasRise?"rgba(224,92,92,.3)":"var(--bor)"}`, borderRadius:10, overflow:"hidden", transition:"border-color .2s" }}>
            <div style={{ padding:"16px 18px" }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", gap:12 }}>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ fontSize:13, fontWeight:500, marginBottom:4, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{f.title}</div>
                  <div style={{ display:"flex", gap:8, flexWrap:"wrap", alignItems:"center", marginBottom:10 }}>
                    <span style={{ fontSize:11, color:"var(--mut)", display:"flex", alignItems:"center", gap:3 }}><MapPin size={10}/>{f.city}</span>
                    <span style={{ fontSize:10, color:"var(--mut)", textTransform:"capitalize" }}>{f.property_type.replace("_"," ")}</span>
                    {f.surface>0&&<span style={{ fontSize:10, color:"var(--mut)" }}>{f.surface} m²</span>}
                    <span style={{ fontSize:9, padding:"1px 5px", borderRadius:999, background:"var(--el)", color:"var(--mut)", border:"1px solid var(--bor)" }}>{f.source}</span>
                  </div>
                  <div style={{ display:"flex", gap:12, alignItems:"center", flexWrap:"wrap" }}>
                    <div>
                      <div style={{ fontSize:9, color:"var(--mut)", marginBottom:2 }}>SAUVEGARDÉ</div>
                      <div style={{ fontSize:12, color:"var(--mut)" }}>{f.saved_price.toLocaleString("fr-TN")} TND</div>
                    </div>
                    <span style={{ color:"var(--mut)", fontSize:14 }}>→</span>
                    <div>
                      <div style={{ fontSize:9, color:"var(--mut)", marginBottom:2 }}>ACTUEL</div>
                      <div style={{ fontSize:14, fontWeight:600, fontFamily:"var(--font-display)", color:"var(--gold)" }}>{f.price.toLocaleString("fr-TN")} TND</div>
                    </div>
                    {delta!==0&&(
                      <div style={{ display:"flex", alignItems:"center", gap:4, padding:"3px 8px", borderRadius:999, background:hasDrop?"rgba(82,200,150,.12)":"rgba(224,92,92,.12)", color:dColor }}>
                        {hasDrop?<TrendingDown size={11}/>:<TrendingUp size={11}/>}
                        <span style={{ fontSize:11, fontWeight:600 }}>{delta>0?"+":""}{deltaP.toFixed(1)}%</span>
                      </div>
                    )}
                    {delta===0&&<span style={{ fontSize:11, color:"var(--mut)" }}>Prix inchangé</span>}
                    {/* Sparkline inline */}
                    <Sparkline saved={f.saved_price} current={f.price}/>
                  </div>
                  <div style={{ fontSize:10, color:"var(--mut)", marginTop:6 }}>Sauvegardé le {new Date(f.saved_at).toLocaleDateString("fr-FR")}</div>
                </div>
                <div style={{ textAlign:"right", flexShrink:0 }}>
                  <div style={{ fontFamily:"var(--font-display)", fontSize:18, fontWeight:600, color:tc }}>{f.trust_score.toFixed(2)}</div>
                  <div style={{ fontSize:9, color:"var(--mut)" }}>trust</div>
                </div>
              </div>

              <div style={{ display:"flex", gap:6, marginTop:12, flexWrap:"wrap" }}>
                <button onClick={()=>setExpanded(e=>e===f.id?null:f.id)} style={{ display:"flex", alignItems:"center", gap:4, padding:"5px 10px", fontSize:11, borderRadius:6, border:"1px solid var(--bor)", background:isExp?"var(--gdim)":"transparent", color:isExp?"var(--gold)":"var(--mut)", cursor:"pointer", fontFamily:"var(--font-body)" }}>
                  {isExp?<ChevronUp size={10}/>:<ChevronDown size={10}/>}{isExp?"Masquer":"Voir historique"}
                </button>
                <button onClick={()=>toggle(f.id)} style={{ display:"flex", alignItems:"center", gap:4, padding:"5px 10px", fontSize:11, borderRadius:6, border:`1px solid ${f.alert_on_price_drop?"var(--gbor)":"var(--bor)"}`, background:f.alert_on_price_drop?"var(--gdim)":"transparent", color:f.alert_on_price_drop?"var(--gold)":"var(--mut)", cursor:"pointer", fontFamily:"var(--font-body)" }}>
                  {f.alert_on_price_drop?<Bell size={10}/>:<BellOff size={10}/>}{f.alert_on_price_drop?"Alerte active":"Activer alerte"}
                </button>
                {f.url&&<a href={f.url} target="_blank" rel="noopener noreferrer" style={{ display:"flex", alignItems:"center", gap:3, padding:"5px 10px", fontSize:11, borderRadius:6, border:"1px solid var(--bor)", color:"var(--mut)", textDecoration:"none" }}><ExternalLink size={9}/>Voir</a>}
                <button onClick={()=>remove(f.id)} style={{ display:"flex", alignItems:"center", gap:3, padding:"5px 10px", fontSize:11, borderRadius:6, border:"1px solid var(--bor)", background:"transparent", color:"var(--bad)", cursor:"pointer", fontFamily:"var(--font-body)", marginLeft:"auto" }}>
                  <Trash2 size={10}/>Retirer
                </button>
              </div>
            </div>

            {/* Graphique historique expandable */}
            {isExp&&(
              <div style={{ borderTop:"1px solid var(--bor)", padding:"0 18px 16px" }}>
                <PriceChart saved={f.saved_price} current={f.price}/>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
