"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LineChart, Line, RadarChart, PolarGrid, PolarAngleAxis, Radar, Legend } from "recharts";
import { RefreshCw, ChevronRight } from "lucide-react";
import { DEMO_MARKET, DEMO_LISTINGS } from "@/lib/demo-listings";

/* ═══════════════════════════════════════════════════════════════════ TERRITORY */
const DEMO_ALERTS = [
  {zone:"Hammamet",alert_type:"emerging",  severity:"critical",price_growth:.152,volume_growth:.284,emergence_score:.82,n_listings_recent:142,median_price_recent:380000,message:"Emerging zone: Hammamet — prices +15.2% and volume +28.4%.",recommendation:"High-potential zone: simultaneous price (+15.2%) and volume (+28.4%) growth. 30–60 day window.",action_horizon_days:30},
  {zone:"Nabeul",  alert_type:"price_surge",severity:"high",   price_growth:.122,volume_growth:.081,emergence_score:.63,n_listings_recent:98, median_price_recent:220000,message:"Price surge in Nabeul: +12.2%.",recommendation:"Strong price increase without corresponding volume rise. Act within 45 days.",action_horizon_days:45},
  {zone:"Mahdia",  alert_type:"volume_surge",severity:"medium",price_growth:.041,volume_growth:.312,emergence_score:.44,n_listings_recent:61, median_price_recent:165000,message:"High activity in Mahdia: 61 listings (+31.2%).",recommendation:"Strong rebound (+31.2%). Prices still stable — short-term opportunity.",action_horizon_days:60},
  {zone:"Ezzahra", alert_type:"emerging",  severity:"high",    price_growth:.098,volume_growth:.187,emergence_score:.58,n_listings_recent:44, median_price_recent:198000,message:"Ezzahra emerging: +9.8% prices, +18.7% volume.",recommendation:"Ben Arous suburb gaining traction. Proximity to Tunis a growth driver.",action_horizon_days:45},
  {zone:"Kasserine",alert_type:"declining",severity:"medium",  price_growth:-.093,volume_growth:-.152,emergence_score:.32,n_listings_recent:18,median_price_recent:85000,message:"Declining zone: Kasserine — −9.3%.",recommendation:"Not recommended for short-term investment.",action_horizon_days:180},
];
const DEMO_TS=[
  {period:"Sep 25",median_price:285000,volume:412},{period:"Oct 25",median_price:292000,volume:441},
  {period:"Nov 25",median_price:298000,volume:388},{period:"Dec 25",median_price:296000,volume:356},
  {period:"Jan 26",median_price:305000,volume:502},{period:"Feb 26",median_price:314000,volume:534},
];
const SEV_COLOR=(s:string)=>s==="critical"?"#cc3b25":s==="high"?"#bf7618":"#4a6fa5";
const ALERT_LABEL:Record<string,string>={emerging:"Emerging zone",price_surge:"Price surge",volume_surge:"Volume surge",declining:"Declining zone"};
const ALERT_ICON:Record<string,string>={emerging:"🚀",price_surge:"📈",volume_surge:"📊",declining:"📉"};

function TerritoryTab() {
  const [alerts,setAlerts]=useState(DEMO_ALERTS);
  const [ts,setTs]=useState(DEMO_TS);
  const [loading,setLoading]=useState(false);
  const [expanded,setExpanded]=useState<string[]>([]);
  const [sev,setSev]=useState<"all"|"critical"|"high"|"medium">("all");

  const refresh=useCallback(async()=>{
    setLoading(true);
    try{const r=await fetch("/api/territorial/alerts?lookback_recent=45",{signal:AbortSignal.timeout(3000)});if(r.ok){const d=await r.json();if(d?.alerts?.length)setAlerts(d.alerts);}}catch{}
    try{const r=await fetch("/api/territorial/timeseries",{signal:AbortSignal.timeout(3000)});if(r.ok){const d=await r.json();if(d?.national?.length)setTs(d.national.slice(-6));}}catch{}
    setLoading(false);
  },[]);
  useEffect(()=>{refresh();},[]);

  const toggleExp=(z:string)=>setExpanded(e=>e.includes(z)?e.filter(x=>x!==z):[...e,z]);
  const filtered=sev==="all"?alerts:alerts.filter(a=>a.severity===sev);

  return (
    <div style={{display:"flex",flexDirection:"column",gap:20}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",flexWrap:"wrap",gap:12}}>
        <div><h2 style={{fontFamily:"Georgia,serif",fontSize:22,fontWeight:600,marginBottom:4}}>Territorial Dynamics</h2><p style={{fontSize:13,color:"#6e7a8a"}}>Time series · Spatial aggregation · Emerging zones</p></div>
        <button onClick={refresh} disabled={loading} className="btn" style={{padding:"8px 14px",fontSize:12}}>
          <RefreshCw size={11} style={{animation:loading?"spin 1s linear infinite":"none",marginRight:5}}/>{loading?"...":"Refresh"}
        </button>
      </div>

      <section className="dash-grid">
        <article className="kpi-card"><span>Critical alerts</span><strong style={{color:"#cc3b25"}}>{alerts.filter(a=>a.severity==="critical").length}</strong><small>Immediate action</small></article>
        <article className="kpi-card"><span>High alerts</span><strong style={{color:"#bf7618"}}>{alerts.filter(a=>a.severity==="high").length}</strong><small>Act within 45 days</small></article>
        <article className="kpi-card"><span>Emerging zones</span><strong style={{color:"#238765"}}>{alerts.filter(a=>a.alert_type==="emerging").length}</strong><small>Growth signal</small></article>
        <article className="kpi-card"><span>Total alerts</span><strong>{alerts.length}</strong><small>Active monitoring</small></article>
      </section>

      <div style={{display:"grid",gridTemplateColumns:"1fr 380px",gap:16,alignItems:"start"}}>
        <div style={{display:"flex",flexDirection:"column",gap:14}}>
          <article className="panel" style={{minHeight:"auto"}}>
            <div className="panel-head"><h3>Monthly evolution — national market</h3></div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={ts}>
                <XAxis dataKey="period" tick={{fill:"#6e7a8a",fontSize:10}} axisLine={false} tickLine={false}/>
                <YAxis yAxisId="p" tick={{fill:"#6e7a8a",fontSize:9}} axisLine={false} tickLine={false} tickFormatter={v=>`${Math.round(v/1000)}K`}/>
                <YAxis yAxisId="v" orientation="right" tick={{fill:"#6e7a8a",fontSize:9}} axisLine={false} tickLine={false}/>
                <Tooltip contentStyle={{background:"white",border:"1px solid #e6eaf0",borderRadius:10,fontSize:11}} formatter={(v:any,name:string)=>[name==="median_price"?`${Number(v).toLocaleString("en-US")} TND`:v,name==="median_price"?"Median price":"Volume"]}/>
                <Line yAxisId="p" type="monotone" dataKey="median_price" stroke="#2f9c7e" strokeWidth={2.5} dot={{fill:"#2f9c7e",r:3}}/>
                <Line yAxisId="v" type="monotone" dataKey="volume" stroke="#bf7618" strokeWidth={1.5} strokeDasharray="5 3" dot={false}/>
              </LineChart>
            </ResponsiveContainer>
          </article>
          <article className="panel" style={{minHeight:"auto"}}>
            <div className="panel-head"><h3>Price/m² by city (top 8)</h3></div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={DEMO_MARKET.cities.slice(0,8).map(c=>({city:c.city,ppm2:c.ppm2}))} layout="vertical" barSize={14}>
                <XAxis type="number" tick={{fill:"#6e7a8a",fontSize:9}} axisLine={false} tickLine={false}/>
                <YAxis type="category" dataKey="city" tick={{fill:"#0b1d33",fontSize:10,fontWeight:600}} axisLine={false} tickLine={false} width={72}/>
                <Tooltip contentStyle={{background:"white",border:"1px solid #e6eaf0",borderRadius:8,fontSize:11}} formatter={(v:any)=>[`${Number(v).toLocaleString("en-US")} TND/m²`]}/>
                <Bar dataKey="ppm2" radius={[0,4,4,0]}>
                  {DEMO_MARKET.cities.slice(0,8).map((_,i)=><Cell key={i} fill={i===0?"#cc3b25":i<=2?"#bf7618":"#2f9c7e"}/>)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </article>
        </div>

        <article className="panel" style={{minHeight:"auto",position:"sticky",top:20}}>
          <div className="panel-head"><h3>Alerts & Recommendations</h3></div>
          <div className="dash-tabs" style={{marginBottom:12}}>
            {(["all","critical","high","medium"] as const).map(s=>(
              <button key={s} className={sev===s?"active":""} onClick={()=>setSev(s)} style={{padding:"8px 12px",fontSize:11}}>
                {s.charAt(0).toUpperCase()+s.slice(1)}
              </button>
            ))}
          </div>
          <div style={{maxHeight:420,overflowY:"auto"}}>
            {filtered.map(a=>{
              const color=SEV_COLOR(a.severity);
              const isExp=expanded.includes(a.zone);
              return (
                <div key={a.zone} style={{background:`${color}08`,border:`1px solid ${color}25`,borderRadius:10,marginBottom:8,overflow:"hidden",cursor:"pointer"}} onClick={()=>toggleExp(a.zone)}>
                  <div style={{padding:"12px 14px",display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
                    <div style={{display:"flex",alignItems:"flex-start",gap:8,flex:1}}>
                      <span style={{fontSize:18,flexShrink:0}}>{ALERT_ICON[a.alert_type]||"📌"}</span>
                      <div>
                        <div style={{display:"flex",alignItems:"center",gap:6,flexWrap:"wrap",marginBottom:3}}>
                          <span style={{fontSize:13,fontWeight:700}}>{a.zone}</span>
                          <span style={{fontSize:10,padding:"2px 7px",borderRadius:999,background:`${color}15`,color,fontWeight:700}}>{ALERT_LABEL[a.alert_type]}</span>
                        </div>
                        <p style={{fontSize:11,color:"#6e7a8a",lineHeight:1.5,margin:0}}>{a.message}</p>
                      </div>
                    </div>
                    <div style={{textAlign:"center",flexShrink:0,marginLeft:8}}>
                      <div style={{fontFamily:"Georgia,serif",fontSize:20,fontWeight:700,color}}>{Math.round(a.emergence_score*100)}</div>
                      <div style={{fontSize:9,color:"#6e7a8a"}}>score</div>
                    </div>
                  </div>
                  {isExp&&(
                    <div style={{padding:"0 14px 12px",borderTop:`1px solid ${color}18`}}>
                      <p style={{fontSize:12,color:"#0b1d33",lineHeight:1.6,marginBottom:8}}>{a.recommendation}</p>
                      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:6}}>
                        {[
                          {l:"Price growth",v:a.price_growth!=null?`${a.price_growth>0?"+":""}${(a.price_growth*100).toFixed(1)}%`:"—"},
                          {l:"Volume growth",v:a.volume_growth!=null?`${a.volume_growth>0?"+":""}${(a.volume_growth*100).toFixed(1)}%`:"—"},
                        ].map(k=>(
                          <div key={k.l} style={{background:"rgba(255,255,255,.7)",borderRadius:8,padding:"6px 8px"}}>
                            <div style={{fontSize:9,color:"#6e7a8a",textTransform:"uppercase",letterSpacing:".05em"}}>{k.l}</div>
                            <div style={{fontSize:12,fontWeight:700,color}}>{k.v}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </article>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════ MAP (3 modes) */
const GOUVERNORATS = [
  {name:"Tunis",     lat:36.8065,lng:10.1815,ppm2:3200,listings:2341,region:"North-East"},
  {name:"Ariana",    lat:36.8663,lng:10.1647,ppm2:2900,listings:892, region:"North-East"},
  {name:"Ben Arous", lat:36.7453,lng:10.2281,ppm2:2700,listings:654, region:"North-East"},
  {name:"Manouba",   lat:36.8101,lng:9.7849, ppm2:2200,listings:431, region:"North-East"},
  {name:"Nabeul",    lat:36.4513,lng:10.7357,ppm2:2600,listings:1203,region:"North-East"},
  {name:"Zaghouan",  lat:36.4029,lng:10.1429,ppm2:1400,listings:124, region:"North"},
  {name:"Bizerte",   lat:37.2744,lng:9.8739, ppm2:1800,listings:456, region:"North"},
  {name:"Béja",      lat:36.7256,lng:9.1817, ppm2:1100,listings:134, region:"North-West"},
  {name:"Jendouba",  lat:36.5012,lng:8.7757, ppm2:900, listings:98,  region:"North-West"},
  {name:"Le Kef",    lat:36.1826,lng:8.7148, ppm2:850, listings:76,  region:"North-West"},
  {name:"Siliana",   lat:36.0849,lng:9.3708, ppm2:780, listings:58,  region:"North-West"},
  {name:"Sousse",    lat:35.8256,lng:10.6369,ppm2:2800,listings:1098,region:"Centre-East"},
  {name:"Monastir",  lat:35.7643,lng:10.8113,ppm2:2600,listings:743, region:"Centre-East"},
  {name:"Mahdia",    lat:35.5047,lng:11.0622,ppm2:1800,listings:312, region:"Centre-East"},
  {name:"Sfax",      lat:34.7398,lng:10.76,  ppm2:2100,listings:876, region:"Centre-East"},
  {name:"Kairouan",  lat:35.6712,lng:10.1006,ppm2:1100,listings:234, region:"Centre"},
  {name:"Kasserine", lat:35.1671,lng:8.8307, ppm2:700, listings:87,  region:"Centre-West"},
  {name:"Sidi Bouzid",lat:35.0382,lng:9.4858,ppm2:650, listings:67,  region:"Centre-West"},
  {name:"Gabès",     lat:33.8881,lng:10.0982,ppm2:1300,listings:198, region:"South"},
  {name:"Médenine",  lat:33.3549,lng:10.5055,ppm2:1500,listings:312, region:"South"},
  {name:"Tataouine", lat:32.9211,lng:10.4518,ppm2:600, listings:43,  region:"South"},
  {name:"Gafsa",     lat:34.425, lng:8.7842, ppm2:800, listings:112, region:"South-West"},
  {name:"Tozeur",    lat:33.9197,lng:8.1336, ppm2:1200,listings:89,  region:"South-West"},
  {name:"Kébili",    lat:33.7038,lng:8.969,  ppm2:700, listings:54,  region:"South-West"},
];

const REGIONS = ["North-East","North","North-West","Centre-East","Centre","Centre-West","South","South-West"];
const REGION_COLORS:Record<string,string> = {
  "North-East":"#2f9c7e","North":"#4a6fa5","North-West":"#7b68c8",
  "Centre-East":"#bf7618","Centre":"#e8a84c","Centre-West":"#cc3b25",
  "South":"#e05c5c","South-West":"#e87c4c",
};
const getPpm2Color=(p:number)=>p<900?"#7b68c8":p<1500?"#4a6fa5":p<2200?"#238765":p<2800?"#bf7618":"#cc3b25";

type MapMode = "circles" | "heatmap" | "clusters";

function MapTab() {
  const [mounted,setMounted]=useState(false);
  const [mapMode,setMapMode]=useState<MapMode>("circles");
  const [subTab,setSubTab]=useState<"map"|"compare"|"radar">("map");
  const [cityA,setCityA]=useState("Hammamet");
  const [cityB,setCityB]=useState("Mahdia");
  const mapRef = useState<any>(null);

  useEffect(()=>{setMounted(true);},[]);

  // Load Leaflet when map tab + circles or heatmap
  useEffect(()=>{
    if(!mounted||subTab!=="map") return;
    // Clean previous map
    const el=document.getElementById("leaflet-map");
    if(!el) return;
    if((el as any)._leaflet_id) {
      // Re-render by clearing
      el.innerHTML="";
      delete (el as any)._leaflet_id;
    }

    const initMap=()=>{
      const L=(window as any).L;
      if(!L||!el) return;
      const map=L.map(el,{zoomControl:true}).setView([34.5,9.2],6);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{attribution:"© OpenStreetMap",maxZoom:18}).addTo(map);
      const minL=Math.min(...GOUVERNORATS.map(g=>g.listings));
      const maxL=Math.max(...GOUVERNORATS.map(g=>g.listings));

      if(mapMode==="circles") {
        GOUVERNORATS.forEach(g=>{
          const r=8+((g.listings-minL)/(maxL-minL))*22;
          const c=getPpm2Color(g.ppm2);
          L.circleMarker([g.lat,g.lng],{radius:r,color:c,fillColor:c,fillOpacity:.6,weight:1.5}).addTo(map)
           .bindPopup(`<div style="font-family:Inter,sans-serif;font-size:12px"><b>${g.name}</b><br/>Price/m²: <b>${g.ppm2.toLocaleString("en-US")} TND</b><br/>Listings: ${g.listings.toLocaleString("en-US")}<br/>Region: ${g.region}</div>`);
        });
      } else if(mapMode==="heatmap") {
        // Large transparent circles = density heatmap simulation
        GOUVERNORATS.forEach(g=>{
          const r=20+((g.listings-minL)/(maxL-minL))*60;
          const c=getPpm2Color(g.ppm2);
          L.circleMarker([g.lat,g.lng],{radius:r,color:"none",fillColor:c,fillOpacity:.22,weight:0}).addTo(map);
          L.circleMarker([g.lat,g.lng],{radius:r*0.4,color:c,fillColor:c,fillOpacity:.55,weight:1}).addTo(map)
           .bindPopup(`<div style="font-family:Inter,sans-serif;font-size:12px"><b>${g.name}</b><br/>Density: <b>${g.listings.toLocaleString("en-US")} listings</b><br/>Price/m²: ${g.ppm2.toLocaleString("en-US")} TND</div>`);
        });
      } else if(mapMode==="clusters") {
        // Group by region — one bubble per region with count
        const byRegion:Record<string,typeof GOUVERNORATS>={};
        GOUVERNORATS.forEach(g=>{ if(!byRegion[g.region])byRegion[g.region]=[]; byRegion[g.region].push(g); });
        Object.entries(byRegion).forEach(([region,cities])=>{
          const avgLat=cities.reduce((s,c)=>s+c.lat,0)/cities.length;
          const avgLng=cities.reduce((s,c)=>s+c.lng,0)/cities.length;
          const total=cities.reduce((s,c)=>s+c.listings,0);
          const avgPpm2=Math.round(cities.reduce((s,c)=>s+c.ppm2,0)/cities.length);
          const r=20+Math.sqrt(total/10);
          const col=REGION_COLORS[region]||"#2f9c7e";
          L.circleMarker([avgLat,avgLng],{radius:r,color:"white",fillColor:col,fillOpacity:.75,weight:2}).addTo(map)
           .bindPopup(`<div style="font-family:Inter,sans-serif;font-size:12px"><b>${region}</b><br/>Listings: <b>${total.toLocaleString("en-US")}</b><br/>Avg price/m²: ${avgPpm2.toLocaleString("en-US")} TND<br/>Cities: ${cities.map(c=>c.name).join(", ")}</div>`);
          // Add count label
          L.marker([avgLat,avgLng],{
            icon:L.divIcon({html:`<div style="background:${col};color:white;border-radius:50%;width:${r*1.2}px;height:${r*1.2}px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;border:2px solid white;box-shadow:0 2px 8px rgba(0,0,0,.25);font-family:Inter,sans-serif">${cities.length}</div>`,iconAnchor:[r*0.6,r*0.6],className:""}),
          }).addTo(map);
        });
      }
    };

    if((window as any).L) {
      initMap();
    } else {
      const link=document.createElement("link");link.rel="stylesheet";link.href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";document.head.appendChild(link);
      const script=document.createElement("script");script.src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
      script.onload=initMap;document.head.appendChild(script);
    }
  },[mounted,subTab,mapMode]);

  const CITIES=["Tunis","Sousse","Hammamet","Nabeul","Sfax","Mahdia","Monastir","Bizerte","La Marsa","Ariana","Tozeur"];
  const SCORES:Record<string,any>={
    Tunis:{price:85,growth:65,volume:90,infra:80,potential:70},
    Sousse:{price:70,growth:75,volume:78,infra:72,potential:78},
    Hammamet:{price:30,growth:88,volume:72,infra:78,potential:85},
    Nabeul:{price:55,growth:80,volume:68,infra:65,potential:76},
    Sfax:{price:72,growth:60,volume:65,infra:68,potential:68},
    Mahdia:{price:80,growth:68,volume:52,infra:58,potential:66},
    Monastir:{price:65,growth:70,volume:60,infra:70,potential:72},
    Bizerte:{price:75,growth:55,volume:55,infra:62,potential:60},
    "La Marsa":{price:20,growth:72,volume:85,infra:88,potential:80},
    Ariana:{price:58,growth:70,volume:75,infra:74,potential:74},
    Tozeur:{price:82,growth:78,volume:40,infra:50,potential:72},
  };
  const COLORS=["#2f9c7e","#bf7618","#cc3b25","#4a6fa5"];
  const radarData=[
    {subject:"Price",   [cityA]:SCORES[cityA]?.price,   [cityB]:SCORES[cityB]?.price},
    {subject:"Growth",  [cityA]:SCORES[cityA]?.growth,  [cityB]:SCORES[cityB]?.growth},
    {subject:"Volume",  [cityA]:SCORES[cityA]?.volume,  [cityB]:SCORES[cityB]?.volume},
    {subject:"Infra",   [cityA]:SCORES[cityA]?.infra,   [cityB]:SCORES[cityB]?.infra},
    {subject:"Potential",[cityA]:SCORES[cityA]?.potential,[cityB]:SCORES[cityB]?.potential},
  ];
  const IS={padding:"9px 12px",borderRadius:12,border:"1px solid #e6eaf0",background:"white",color:"#0b1d33",fontFamily:"Inter,sans-serif",fontSize:13,cursor:"pointer"} as const;

  return (
    <div style={{display:"flex",flexDirection:"column",gap:16}}>
      <div><h2 style={{fontFamily:"Georgia,serif",fontSize:22,fontWeight:600,marginBottom:4}}>Market Map</h2><p style={{fontSize:13,color:"#6e7a8a"}}>Spatial visualisation · Zone comparator · Attractiveness radar</p></div>

      {/* Main sub-tabs */}
      <section className="dash-tabs">
        {(["map","compare","radar"] as const).map(id=>(
          <button key={id} className={subTab===id?"active":""} onClick={()=>setSubTab(id)}>
            {id==="map"?"Interactive Map":id==="compare"?"Zone Comparator":"Attractiveness Radar"}
          </button>
        ))}
      </section>

      {/* ── MAP with 3 mode toggles ── */}
      {subTab==="map"&&(
        <div style={{display:"flex",flexDirection:"column",gap:10}}>
          {/* Map mode selector */}
          <div style={{display:"flex",gap:0,background:"rgba(255,255,255,.8)",borderRadius:14,padding:5,width:"max-content",border:"1px solid rgba(255,255,255,.9)",boxShadow:"0 4px 12px rgba(7,29,51,.06)"}}>
            {([
              {id:"circles" as const,  label:"📍 Circles",  desc:"Price/m² by marker size"},
              {id:"heatmap" as const,  label:"🌡 Heatmap",  desc:"Listing density"},
              {id:"clusters" as const, label:"🔵 Clusters",  desc:"Grouped by region"},
            ]).map(mode=>(
              <button key={mode.id} onClick={()=>setMapMode(mode.id)} style={{
                padding:"9px 18px",borderRadius:10,border:"none",cursor:"pointer",fontFamily:"Inter,sans-serif",
                background:mapMode===mode.id?"#071d33":"transparent",
                color:mapMode===mode.id?"white":"#6e7a8a",
                fontWeight:mapMode===mode.id?800:600,fontSize:13,
                transition:"all .2s",
              }}>
                {mode.label}
              </button>
            ))}
          </div>

          {/* Map description */}
          <p style={{fontSize:12,color:"#6e7a8a",padding:"6px 12px",background:"rgba(7,29,51,.04)",borderRadius:8,margin:0}}>
            {mapMode==="circles"?"Circle size = listing count · Color = price/m² (green = medium, red = premium, blue = affordable)":
             mapMode==="heatmap"?"Heat intensity = listing density concentration by governorate · Larger glow = more active market":
             "Grouped by region · Bubble size = market volume · Click for details"}
          </p>

          {/* Map container */}
          <article className="panel" style={{minHeight:"auto",padding:0,overflow:"hidden",borderRadius:20}}>
            <div id="leaflet-map" style={{height:480,background:"#e8f0e9"}}>
              {!mounted&&<div style={{display:"flex",alignItems:"center",justifyContent:"center",height:"100%",color:"#6e7a8a"}}>Loading map...</div>}
            </div>
            {/* Legend */}
            <div style={{padding:"10px 16px",display:"flex",gap:16,flexWrap:"wrap",fontSize:11,color:"#6e7a8a",borderTop:"1px solid #e6eaf0"}}>
              {mapMode==="circles"||mapMode==="heatmap"?[
                {c:"#cc3b25",l:"Premium > 2,800 TND/m²"},{c:"#bf7618",l:"High 2,200–2,800"},
                {c:"#238765",l:"Medium 1,500–2,200"},{c:"#4a6fa5",l:"Affordable < 1,500"}
              ].map(x=>(
                <div key={x.l} style={{display:"flex",alignItems:"center",gap:5}}>
                  <div style={{width:10,height:10,borderRadius:"50%",background:x.c}}/>{x.l}
                </div>
              )):[
                ...REGIONS.slice(0,4).map(r=>({c:REGION_COLORS[r],l:r}))
              ].map(x=>(
                <div key={x.l} style={{display:"flex",alignItems:"center",gap:5}}>
                  <div style={{width:10,height:10,borderRadius:"50%",background:x.c}}/>{x.l}
                </div>
              ))}
            </div>
          </article>
        </div>
      )}

      {/* ── COMPARATOR ── */}
      {subTab==="compare"&&(
        <div style={{display:"flex",flexDirection:"column",gap:16}}>
          <div style={{display:"flex",gap:12,flexWrap:"wrap"}}>
            {[{val:cityA,set:setCityA,col:COLORS[0],lbl:"City A"},{val:cityB,set:setCityB,col:COLORS[1],lbl:"City B"}].map((c,i)=>(
              <div key={i} style={{display:"flex",alignItems:"center",gap:8}}>
                <div style={{width:12,height:12,borderRadius:"50%",background:c.col}}/>
                <label style={{fontSize:11,color:"#6e7a8a",fontWeight:700}}>{c.lbl}</label>
                <select value={c.val} onChange={e=>c.set(e.target.value)} style={IS}>
                  {CITIES.map(city=><option key={city}>{city}</option>)}
                </select>
              </div>
            ))}
          </div>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:16}}>
            {[{city:cityA,col:COLORS[0]},{city:cityB,col:COLORS[1]}].map(({city,col})=>{
              const sc=SCORES[city]||{};
              const avg=Math.round(Object.values(sc as Record<string,number>).reduce((a,b)=>a+b,0)/Math.max(Object.keys(sc).length,1));
              return (
                <article key={city} className="panel" style={{minHeight:"auto",textAlign:"center"}}>
                  <div style={{fontSize:17,fontWeight:800,color:col,marginBottom:14}}>{city}</div>
                  <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8,marginBottom:12}}>
                    {[{l:"PRICE",v:sc.price},{l:"GROWTH",v:sc.growth},{l:"VOLUME",v:sc.volume},{l:"INFRA",v:sc.infra},{l:"POTENTIAL",v:sc.potential}].filter(k=>k.v!==undefined).map(k=>(
                      <div key={k.l} style={{background:"rgba(7,29,51,.03)",borderRadius:10,padding:10}}>
                        <div style={{fontFamily:"Georgia,serif",fontSize:22,fontWeight:700,color:col}}>{k.v}</div>
                        <div style={{fontSize:9,color:"#6e7a8a",textTransform:"uppercase",letterSpacing:".06em"}}>{k.l}</div>
                        <div style={{height:4,background:"#e6eaf0",borderRadius:2,marginTop:4,overflow:"hidden"}}><div style={{height:"100%",width:`${k.v}%`,background:col,borderRadius:2}}/></div>
                      </div>
                    ))}
                  </div>
                  <div style={{fontFamily:"Georgia,serif",fontSize:30,fontWeight:700,color:"#071d33"}}>{avg}<span style={{fontSize:14,color:"#6e7a8a",fontFamily:"Inter,sans-serif"}}> / 100</span></div>
                </article>
              );
            })}
          </div>
          <div style={{padding:"12px 18px",background:"rgba(47,156,126,.07)",border:"1px solid rgba(47,156,126,.25)",borderRadius:14,fontSize:13,fontWeight:700,color:"#071d33",textAlign:"center"}}>
            {(()=>{
              const sA=SCORES[cityA],sB=SCORES[cityB];
              if(!sA||!sB) return "Select two cities";
              const avgA=Math.round(Object.values(sA as Record<string,number>).reduce((a,b)=>a+b,0)/Object.keys(sA).length);
              const avgB=Math.round(Object.values(sB as Record<string,number>).reduce((a,b)=>a+b,0)/Object.keys(sB).length);
              return avgA>avgB?`${cityA} is more attractive overall (+${avgA-avgB} pts)`:avgB>avgA?`${cityB} is more attractive overall (+${avgB-avgA} pts)`:"Both zones equally attractive";
            })()}
          </div>
        </div>
      )}

      {/* ── RADAR ── */}
      {subTab==="radar"&&(
        <div style={{display:"flex",flexDirection:"column",gap:14}}>
          <div style={{display:"flex",gap:12,flexWrap:"wrap"}}>
            {[{val:cityA,set:setCityA,col:COLORS[0]},{val:cityB,set:setCityB,col:COLORS[1]}].map((c,i)=>(
              <div key={i} style={{display:"flex",alignItems:"center",gap:8}}>
                <div style={{width:12,height:12,borderRadius:"50%",background:c.col}}/>
                <select value={c.val} onChange={e=>c.set(e.target.value)} style={IS}>
                  {CITIES.map(city=><option key={city}>{city}</option>)}
                </select>
              </div>
            ))}
          </div>
          <article className="panel" style={{minHeight:"auto",display:"flex",justifyContent:"center"}}>
            <ResponsiveContainer width="100%" height={380}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#e6eaf0"/>
                <PolarAngleAxis dataKey="subject" tick={{fill:"#6e7a8a",fontSize:11}}/>
                <Radar name={cityA} dataKey={cityA} stroke={COLORS[0]} fill={COLORS[0]} fillOpacity={.22}/>
                <Radar name={cityB} dataKey={cityB} stroke={COLORS[1]} fill={COLORS[1]} fillOpacity={.15}/>
                <Legend/>
              </RadarChart>
            </ResponsiveContainer>
          </article>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════ MARKET (with local filter) */
function MarketTab() {
  // allCities is now DEMO_LISTINGS (real dataset)
  const [city,    setCity]    = useState("");
  const [type,    setType]    = useState("");
  const [data,    setData]    = useState(DEMO_MARKET);
  const [loading, setLoading] = useState(false);

  // Apply local filter from LISTINGS dataset — always works, real data
  const applyFilter = useCallback(async()=>{
    setLoading(true);

    // Filter listings by city and type
    let items = [...DEMO_LISTINGS];
    if(city.trim()) items = items.filter((l:any)=>l.city.toLowerCase().includes(city.toLowerCase().trim()));
    if(type)        items = items.filter((l:any)=>l.property_type===type);

    // Group by city to compute median ppm2
    const byCityMap:Record<string,number[]>={};
    items.forEach((l:any)=>{if(!byCityMap[l.city])byCityMap[l.city]=[];byCityMap[l.city].push(l.price_per_m2);});
    const filteredWithType = Object.entries(byCityMap)
      .map(([c,ppms]:any)=>({city:c,ppm2:Math.round(ppms.reduce((a:number,b:number)=>a+b,0)/ppms.length),n:ppms.length}))
      .sort((a,b)=>b.ppm2-a.ppm2);

    const allPpms = items.map((l:any)=>l.price_per_m2).sort((a:number,b:number)=>a-b);
    const median = allPpms.length?allPpms[Math.floor(allPpms.length/2)]:DEMO_MARKET.median_ppm2;
    const topCity = filteredWithType[0]?.city||DEMO_MARKET.top_city;

    setData({total:items.length,median_ppm2:median,top_city:topCity,cities:filteredWithType.length?filteredWithType:DEMO_MARKET.cities});

    // Try API (enhance with real data if backend running)
    try {
      const p=new URLSearchParams();
      if(city)p.set("city",city);if(type)p.set("property_type",type);
      const r=await fetch(`/api/market?${p}`,{signal:AbortSignal.timeout(3000)});
      if(r.ok){const d=await r.json();if(d.cities?.length)setData(d);}
    } catch {}
    setLoading(false);
  },[city,type]);

  const resetFilter=()=>{setCity("");setType("");setData({...DEMO_MARKET,total:DEMO_LISTINGS.length});};

  const sorted=[...data.cities].sort((a,b)=>b.ppm2-a.ppm2);
  const max=sorted[0]?.ppm2||1;
  const IS={padding:"9px 12px",borderRadius:12,border:"1px solid #e6eaf0",background:"white",color:"#0b1d33",fontFamily:"Inter,sans-serif",fontSize:13,outline:"none"} as const;

  return (
    <div style={{display:"flex",flexDirection:"column",gap:20}}>
      <div><h2 style={{fontFamily:"Georgia,serif",fontSize:22,fontWeight:600,marginBottom:4}}>Market Overview</h2><p style={{fontSize:13,color:"#6e7a8a"}}>Price per m² and statistics by city and property type</p></div>

      {/* Filters */}
      <div style={{display:"flex",gap:12,flexWrap:"wrap",alignItems:"flex-end"}}>
        <div>
          <label style={{fontSize:10,color:"#6e7a8a",display:"block",marginBottom:5,textTransform:"uppercase",letterSpacing:".06em",fontWeight:700}}>City</label>
          <input value={city} onChange={e=>setCity(e.target.value)} onKeyDown={e=>e.key==="Enter"&&applyFilter()} placeholder="All cities" style={{...IS,width:200}}/>
        </div>
        <div>
          <label style={{fontSize:10,color:"#6e7a8a",display:"block",marginBottom:5,textTransform:"uppercase",letterSpacing:".06em",fontWeight:700}}>Property type</label>
          <select value={type} onChange={e=>setType(e.target.value)} style={{...IS,width:170,cursor:"pointer"}}>
            <option value="">All types</option>
            {["apartment","villa","land","house","studio","commercial"].map(t=><option key={t}>{t}</option>)}
          </select>
        </div>
        <button onClick={applyFilter} disabled={loading} style={{padding:"10px 22px",borderRadius:14,border:"none",background:"linear-gradient(135deg,#2f9c7e,#1e7d63)",color:"white",fontWeight:800,cursor:"pointer",fontSize:13,fontFamily:"Inter,sans-serif",boxShadow:"0 8px 20px rgba(47,156,126,.28)",opacity:loading?.7:1}}>
          {loading?"...":"Filter"}
        </button>
        {(city||type)&&<button onClick={resetFilter} style={{padding:"10px 16px",borderRadius:14,border:"1px solid #e6eaf0",background:"white",color:"#6e7a8a",cursor:"pointer",fontSize:13,fontFamily:"Inter,sans-serif"}}>Reset</button>}
      </div>

      {/* KPIs */}
      <section className="dash-grid" style={{gridTemplateColumns:"repeat(3,1fr)"}}>
        <article className="kpi-card"><span>National median price</span><strong>{data.median_ppm2?.toLocaleString("en-US")} TND/m²</strong><small>{DEMO_LISTINGS.length} listings indexed</small></article>
        <article className="kpi-card"><span>Most expensive city</span><strong style={{color:"#cc3b25",fontSize:26}}>{data.top_city}</strong><small>{sorted[0]?.ppm2?.toLocaleString("en-US")} TND/m² median</small></article>
        <article className="kpi-card"><span>Cities covered</span><strong style={{color:"#238765"}}>{data.cities.length}</strong><small>Governorates analysed</small></article>
      </section>

      {/* Chart */}
      <article className="panel" style={{minHeight:"auto"}}>
        <div className="panel-head"><h3>Median price per m² by city (TND){type&&<span style={{fontSize:12,color:"#6e7a8a",marginLeft:8}}>· {type}</span>}</h3></div>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={sorted} barSize={type?"42":"36" as any}>
            <XAxis dataKey="city" tick={{fill:"#6e7a8a",fontSize:10}} axisLine={false} tickLine={false}/>
            <YAxis tick={{fill:"#6e7a8a",fontSize:9}} axisLine={false} tickLine={false} tickFormatter={v=>v.toLocaleString("en-US")}/>
            <Tooltip contentStyle={{background:"white",border:"1px solid #e6eaf0",borderRadius:10,fontSize:12}} formatter={(v:any)=>[`${Number(v).toLocaleString("en-US")} TND/m²`,"Price/m²"]}/>
            <Bar dataKey="ppm2" radius={[5,5,0,0]}>
              {sorted.map((_,i)=><Cell key={i} fill={i===0?"#cc3b25":i<=2?"#bf7618":"#2f9c7e"}/>)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </article>

      {/* Table */}
      <article className="panel" style={{minHeight:"auto"}}>
        <div className="panel-head"><h3>Detail by city ({sorted.length} results)</h3></div>
        <table>
          <thead><tr><th>City</th><th>Listings</th><th>Median price/m²</th><th>Rank</th></tr></thead>
          <tbody>
            {sorted.map((c,i)=>(
              <tr key={c.city}>
                <td style={{fontWeight:600}}>{c.city}</td>
                <td style={{color:"#6e7a8a"}}>{c.n?.toLocaleString("en-US")}</td>
                <td>
                  <div style={{display:"flex",alignItems:"center",gap:8}}>
                    <div style={{width:80,height:6,background:"#e6eaf0",borderRadius:3,overflow:"hidden"}}>
                      <div style={{height:"100%",width:`${c.ppm2/max*100}%`,background:i===0?"#cc3b25":i<=2?"#bf7618":"#2f9c7e",borderRadius:3}}/>
                    </div>
                    <span style={{fontWeight:700}}>{c.ppm2?.toLocaleString("en-US")} TND</span>
                  </div>
                </td>
                <td><span className={`risk ${i===0?"high":i<=2?"mid":"low"}`}>#{i+1}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </article>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════ BO2 PAGE */
type Tab = "territory"|"map"|"market";
const TABS:{id:Tab;label:string}[] = [{id:"territory",label:"Territory"},{id:"map",label:"Map"},{id:"market",label:"Market"}];

export default function BO2Page() {
  const [tab,setTab]=useState<Tab>("territory");
  const params=useSearchParams();
  useEffect(()=>{const t=params.get("tab") as Tab|null;if(t&&TABS.find(x=>x.id===t))setTab(t);},[params]);

  return (
    <>
      <header className="dash-header">
        <div>
          <span className="eyebrow">Smart Dashboard</span>
          <h1>BO2 — Territorial Dynamics</h1>
        </div>
        <div className="header-actions">
          <div className="dash-search">
            <img src="/assets/icons/house.png" alt=""/>
            <input placeholder="Search a listing, city, score..." readOnly/>
          </div>
          <button className="icon-btn"><img src="/assets/icons/bell.png" alt=""/></button>
          <div className="profile">
            <img src="/assets/avatar-director.png" alt="Admin"/>
            <span>Admin</span>
          </div>
        </div>
      </header>

      <section className="dash-tabs">
        {TABS.map(t=>(
          <button key={t.id} className={tab===t.id?"active":""} onClick={()=>setTab(t.id)}>{t.label}</button>
        ))}
      </section>

      <div className="animate-in">
        {tab==="territory" && <TerritoryTab/>}
        {tab==="map"       && <MapTab/>}
        {tab==="market"    && <MarketTab/>}
      </div>

      <footer className="dash-footer">Estate Mind © 2026 · AI Real Estate Intelligence</footer>
    </>
  );
}
