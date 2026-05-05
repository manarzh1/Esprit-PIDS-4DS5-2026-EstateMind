"use client";
import { useEffect, useRef, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
  RadarChart, PolarGrid, PolarAngleAxis, Radar,
} from "recharts";
import { Map, BarChart2, Star } from "lucide-react";

const GOUVERNORATS = [
  {name:"Tunis",lat:36.8065,lng:10.1815,ppm2:3200,listings:2341,region:"North-East",median:280000},
  {name:"Ariana",lat:36.8663,lng:10.1647,ppm2:2900,listings:892,region:"North-East",median:245000},
  {name:"Ben Arous",lat:36.7453,lng:10.2281,ppm2:2700,listings:654,region:"North-East",median:220000},
  {name:"Manouba",lat:36.8101,lng:9.7849,ppm2:2200,listings:431,region:"North-East",median:185000},
  {name:"Nabeul",lat:36.4513,lng:10.7357,ppm2:2600,listings:1203,region:"North-East",median:210000},
  {name:"Zaghouan",lat:36.4029,lng:10.1429,ppm2:1400,listings:124,region:"North",median:120000},
  {name:"Bizerte",lat:37.2744,lng:9.8739,ppm2:1800,listings:456,region:"North",median:155000},
  {name:"Béja",lat:36.7256,lng:9.1817,ppm2:1100,listings:134,region:"North-West",median:95000},
  {name:"Jendouba",lat:36.5012,lng:8.7757,ppm2:900,listings:98,region:"North-West",median:78000},
  {name:"Le Kef",lat:36.1826,lng:8.7148,ppm2:850,listings:76,region:"North-West",median:72000},
  {name:"Siliana",lat:36.0849,lng:9.3708,ppm2:780,listings:58,region:"North-West",median:65000},
  {name:"Sousse",lat:35.8256,lng:10.6369,ppm2:2800,listings:1098,region:"Centre-East",median:235000},
  {name:"Monastir",lat:35.7643,lng:10.8113,ppm2:2600,listings:743,region:"Centre-East",median:215000},
  {name:"Mahdia",lat:35.5047,lng:11.0622,ppm2:1800,listings:312,region:"Centre-East",median:155000},
  {name:"Sfax",lat:34.7398,lng:10.76,ppm2:2100,listings:876,region:"Centre-East",median:175000},
  {name:"Kairouan",lat:35.6712,lng:10.1006,ppm2:1100,listings:234,region:"Centre",median:92000},
  {name:"Kasserine",lat:35.1671,lng:8.8307,ppm2:700,listings:87,region:"Centre-West",median:58000},
  {name:"Sidi Bouzid",lat:35.0382,lng:9.4858,ppm2:650,listings:67,region:"Centre-West",median:54000},
  {name:"Gabès",lat:33.8881,lng:10.0982,ppm2:1300,listings:198,region:"South",median:110000},
  {name:"Médenine",lat:33.3549,lng:10.5055,ppm2:1500,listings:312,region:"South",median:128000},
  {name:"Tataouine",lat:32.9211,lng:10.4518,ppm2:600,listings:43,region:"South",median:48000},
  {name:"Gafsa",lat:34.425,lng:8.7842,ppm2:800,listings:112,region:"South-West",median:68000},
  {name:"Tozeur",lat:33.9197,lng:8.1336,ppm2:1200,listings:89,region:"South-West",median:102000},
  {name:"Kébili",lat:33.7038,lng:8.969,ppm2:700,listings:54,region:"South-West",median:57000},
];

const getColor=(ppm2:number)=>ppm2<800?"#4a6fa5":ppm2<1500?"#6b9fe8":ppm2<2200?"#238765":ppm2<2800?"#bf7618":"#cc3b25";

const CITIES_FOR_COMPARE=["Tunis","Sousse","Hammamet","Nabeul","Sfax","Mahdia","Monastir","Bizerte"];
const CITY_SCORES:Record<string,any>={
  Tunis:    {price:85,growth:65,volume:90,infra:80,potential:70,growth_pct:8.6},
  Sousse:   {price:70,growth:75,volume:78,infra:72,potential:78,growth_pct:10.2},
  Hammamet: {price:30,growth:85,volume:72,infra:78,potential:82,growth_pct:15.2},
  Nabeul:   {price:55,growth:80,volume:68,infra:65,potential:76,growth_pct:12.2},
  Sfax:     {price:72,growth:60,volume:65,infra:68,potential:68,growth_pct:6.4},
  Mahdia:   {price:80,growth:68,volume:52,infra:58,potential:66,growth_pct:8.4},
  Monastir: {price:65,growth:70,volume:60,infra:70,potential:72,growth_pct:9.1},
  Bizerte:  {price:75,growth:55,volume:55,infra:62,potential:60,growth_pct:5.2},
};
const COMPARE_HISTORY:Record<string,number[]>={
  Tunis:[295000,302000,308000,305000,311000,315000],
  Sousse:[235000,240000,244000,241000,247000,248000],
  Hammamet:[330000,345000,358000,364000,372000,380000],
  Nabeul:[196000,205000,212000,209000,216000,220000],
  Sfax:[162000,165000,167000,166000,169000,171000],
};
const MONTHS=["Sep 25","Oct 25","Nov 25","Dec 25","Jan 26","Feb 26"];
const COLORS=["#2f9c7e","#bf7618","#cc3b25","#4a6fa5","#7b68c8","#e87c4c"];

type SubTab="map"|"compare"|"radar";

export default function MapSection() {
  const mapRef=useRef<any>(null);
  const mapContainerRef=useRef<HTMLDivElement>(null);
  const markersRef=useRef<any[]>([]);
  const [subTab,setSubTab]=useState<SubTab>("map");
  const [layer,setLayer]=useState("price");
  const [compareA,setCompareA]=useState("Hammamet");
  const [compareB,setCompareB]=useState("Mahdia");
  const [compareData,setCompareData]=useState<any[]>([]);
  const [radarData,setRadarData]=useState<any[]>([]);
  const [mounted,setMounted]=useState(false);

  useEffect(()=>{ setMounted(true); },[]);

  // Build compare chart data
  useEffect(()=>{
    const dataA=COMPARE_HISTORY[compareA]||COMPARE_HISTORY["Tunis"];
    const dataB=COMPARE_HISTORY[compareB]||COMPARE_HISTORY["Sousse"];
    setCompareData(MONTHS.map((m,i)=>({month:m,[compareA]:dataA[i],[compareB]:dataB[i]})));
  },[compareA,compareB]);

  // Build radar data
  useEffect(()=>{
    const a=CITY_SCORES[compareA]||{price:50,growth:50,volume:50,infra:50,potential:50};
    const b=CITY_SCORES[compareB]||{price:50,growth:50,volume:50,infra:50,potential:50};
    setRadarData([
      {subject:"price",    [compareA]:a.price,    [compareB]:b.price},
      {subject:"growth",   [compareA]:a.growth,   [compareB]:b.growth},
      {subject:"volume",   [compareA]:a.volume,   [compareB]:b.volume},
      {subject:"infra",    [compareA]:a.infra,    [compareB]:b.infra},
      {subject:"potential",[compareA]:a.potential,[compareB]:b.potential},
    ]);
  },[compareA,compareB]);

  // Leaflet map
  useEffect(()=>{
    if(!mounted||subTab!=="map"||typeof window==="undefined") return;
    if(mapRef.current) { mapRef.current.remove(); mapRef.current=null; }
    const L=(window as any).L;
    if(!L||!mapContainerRef.current) return;
    const map=L.map(mapContainerRef.current,{zoomControl:true}).setView([34.5,9.2],6);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{attribution:"© OpenStreetMap",maxZoom:18}).addTo(map);
    mapRef.current=map;

    const minL=Math.min(...GOUVERNORATS.map(g=>g.listings));
    const maxL=Math.max(...GOUVERNORATS.map(g=>g.listings));
    GOUVERNORATS.forEach(g=>{
      const r=8+((g.listings-minL)/(maxL-minL))*26;
      const col=getColor(g.ppm2);
      L.circleMarker([g.lat,g.lng],{radius:r,color:col,fillColor:col,fillOpacity:.55,weight:1.5}).addTo(map)
       .bindPopup(`<div style="font-family:Inter,sans-serif;font-size:12px"><strong>${g.name}</strong><br/>Price/m²: <strong>${g.ppm2.toLocaleString("en-US")} TND</strong><br/>Listings: ${g.listings.toLocaleString("en-US")}<br/>Region: ${g.region}</div>`);
    });

    return ()=>{ if(mapRef.current){mapRef.current.remove();mapRef.current=null;} };
  },[mounted,subTab,layer]);

  const scoreA=CITY_SCORES[compareA]||{};
  const scoreB=CITY_SCORES[compareB]||{};

  return (
    <div style={{display:"flex",flexDirection:"column",gap:14}}>
      <div className="dash-topbar">
        <div>
          <h1>Market Map</h1>
          <p>Spatial visualisation · Zone comparator · Attractiveness radar</p>
        </div>
      </div>

      {/* Sub-tabs */}
      <div className="bo-tabs">
        {([["map","Interactive Map"],["compare","Zone Comparator"],["radar","Attractiveness Radar"]] as const).map(([id,label])=>(
          <button key={id} className={`bo-tab${subTab===id?" active":""}`} onClick={()=>setSubTab(id as SubTab)}>{label}</button>
        ))}
      </div>

      {/* MAP */}
      {subTab==="map"&&(
        <div style={{display:"flex",flexDirection:"column",gap:10}}>
          <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
            {["price","region","listings"].map(l=>(
              <button key={l} className={`bo-tab${layer===l?" active":""}`} style={{fontSize:11,padding:"5px 12px"}} onClick={()=>setLayer(l)}>
                {l==="price"?"Price/m²":l==="region"?"Region":l==="listings"?"Listings":""}
              </button>
            ))}
          </div>
          <div style={{position:"relative",height:500,borderRadius:16,overflow:"hidden",border:"1px solid var(--line)",boxShadow:"0 8px 24px rgba(7,29,51,.08)"}}>
            {mounted?(
              <>
                <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
                <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" async/>
                <div ref={mapContainerRef} style={{height:"100%",width:"100%",background:"#e8f0e9"}}/>
              </>
            ):<div style={{height:"100%",display:"flex",alignItems:"center",justifyContent:"center",color:"var(--mut)"}}>Loading map...</div>}
          </div>
          <div style={{display:"flex",gap:10,flexWrap:"wrap"}}>
            {[{c:"#cc3b25",l:"Premium > 2,800 TND"},{c:"#bf7618",l:"High 1,500–2,800 TND"},{c:"#238765",l:"Medium 800–1,500 TND"},{c:"#4a6fa5",l:"Affordable < 800 TND"}].map(x=>(
              <div key={x.l} style={{display:"flex",alignItems:"center",gap:5,fontSize:11,color:"var(--mut)"}}>
                <div style={{width:10,height:10,borderRadius:"50%",background:x.c,flexShrink:0}}/>
                {x.l}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* COMPARATOR */}
      {subTab==="compare"&&(
        <div style={{display:"flex",flexDirection:"column",gap:14}}>
          <div style={{display:"flex",gap:10,alignItems:"center",flexWrap:"wrap"}}>
            {[{val:compareA,set:setCompareA,label:"City A"},{val:compareB,set:setCompareB,label:"City B"}].map((c,i)=>(
              <div key={i} style={{display:"flex",alignItems:"center",gap:8}}>
                <div style={{width:12,height:12,borderRadius:"50%",background:COLORS[i],flexShrink:0}}/>
                <select value={c.val} onChange={e=>c.set(e.target.value)} style={{padding:"8px 12px",borderRadius:10,border:"1px solid var(--line)",background:"white",color:"var(--txt)",fontFamily:"var(--font-body)",fontSize:12,fontWeight:600,cursor:"pointer"}}>
                  {CITIES_FOR_COMPARE.map(city=><option key={city} value={city}>{city}</option>)}
                </select>
              </div>
            ))}
          </div>

          <div className="panel">
            <div className="panel-head"><h3>Price evolution comparison</h3></div>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={compareData}>
                <XAxis dataKey="month" tick={{fill:"var(--mut)",fontSize:10}} axisLine={false} tickLine={false}/>
                <YAxis tick={{fill:"var(--mut)",fontSize:9}} axisLine={false} tickLine={false} tickFormatter={v=>`${Math.round(v/1000)}K`}/>
                <Tooltip contentStyle={{background:"white",border:"1px solid var(--line)",borderRadius:10,fontSize:11}} formatter={(v:any,name:string)=>[`${Number(v).toLocaleString("en-US")} TND`,name]}/>
                <Legend/>
                <Line type="monotone" dataKey={compareA} stroke={COLORS[0]} strokeWidth={2.5} dot={{fill:COLORS[0],r:4}}/>
                <Line type="monotone" dataKey={compareB} stroke={COLORS[1]} strokeWidth={2.5} dot={{fill:COLORS[1],r:4}}/>
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
            {[{city:compareA,sc:scoreA,col:COLORS[0]},{city:compareB,sc:scoreB,col:COLORS[1]}].map(({city,sc,col})=>(
              <div key={city} className="panel" style={{textAlign:"center"}}>
                <div style={{fontSize:16,fontWeight:700,color:col,marginBottom:14}}>{city}</div>
                <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8,marginBottom:10}}>
                  {[{l:"PRICE",v:sc.price},{l:"GROWTH",v:sc.growth},{l:"VOLUME",v:sc.volume},{l:"INFRA",v:sc.infra}].map(k=>(
                    <div key={k.l} style={{background:"rgba(7,29,51,.03)",borderRadius:8,padding:8}}>
                      <div style={{fontFamily:"var(--font-display)",fontSize:22,fontWeight:700,color:col}}>{k.v}</div>
                      <div style={{fontSize:9,color:"var(--mut)",textTransform:"uppercase",letterSpacing:".06em"}}>{k.l}</div>
                      <div style={{height:4,background:"var(--line)",borderRadius:2,marginTop:4,overflow:"hidden"}}>
                        <div style={{height:"100%",width:`${k.v}%`,background:col,borderRadius:2}}/>
                      </div>
                    </div>
                  ))}
                </div>
                <div style={{fontSize:13,color:col,fontWeight:700}}>↑ +{sc.growth_pct}% · {GOUVERNORATS.find(g=>g.name===city)?.ppm2?.toLocaleString("en-US")||"—"} TND/m²</div>
                <div style={{fontFamily:"var(--font-display)",fontSize:28,fontWeight:700,color:"var(--navy)",marginTop:8}}>
                  {Math.round((sc.price+sc.growth+sc.volume+sc.infra+sc.potential)/5)} <span style={{fontSize:14,color:"var(--mut)"}}>score/100</span>
                </div>
              </div>
            ))}
          </div>
          <div style={{padding:"12px 16px",background:"rgba(47,156,126,.06)",borderRadius:10,border:"1px solid rgba(47,156,126,.2)",fontSize:13,fontWeight:600,color:"var(--navy)",textAlign:"center"}}>
            {(()=>{
              const sA=Math.round((scoreA.price+scoreA.growth+scoreA.volume+scoreA.infra+scoreA.potential)/5);
              const sB=Math.round((scoreB.price+scoreB.growth+scoreB.volume+scoreB.infra+scoreB.potential)/5);
              return sA>sB?`${compareA} is more attractive (+${sA-sB} pts)`:sB>sA?`${compareB} is more attractive (+${sB-sA} pts)`:"Both zones are equally attractive";
            })()}
          </div>
        </div>
      )}

      {/* RADAR */}
      {subTab==="radar"&&(
        <div style={{display:"flex",flexDirection:"column",gap:14}}>
          <div style={{display:"flex",gap:10,alignItems:"center",flexWrap:"wrap"}}>
            {[{val:compareA,set:setCompareA},{val:compareB,set:setCompareB}].map((c,i)=>(
              <div key={i} style={{display:"flex",alignItems:"center",gap:8}}>
                <div style={{width:12,height:12,borderRadius:"50%",background:COLORS[i],flexShrink:0}}/>
                <select value={c.val} onChange={e=>c.set(e.target.value)} style={{padding:"8px 12px",borderRadius:10,border:"1px solid var(--line)",background:"white",color:"var(--txt)",fontFamily:"var(--font-body)",fontSize:12,fontWeight:600,cursor:"pointer"}}>
                  {CITIES_FOR_COMPARE.map(city=><option key={city} value={city}>{city}</option>)}
                </select>
                <button className="btn" onClick={()=>{}} style={{fontSize:11,padding:"5px 12px"}}>Compare</button>
              </div>
            ))}
          </div>

          <div className="panel" style={{display:"flex",justifyContent:"center",padding:24}}>
            <ResponsiveContainer width="100%" height={360}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="var(--line)"/>
                <PolarAngleAxis dataKey="subject" tick={{fill:"var(--mut)",fontSize:11}}/>
                <Radar name={compareA} dataKey={compareA} stroke={COLORS[0]} fill={COLORS[0]} fillOpacity={.22}/>
                <Radar name={compareB} dataKey={compareB} stroke={COLORS[1]} fill={COLORS[1]} fillOpacity={.15}/>
                <Legend/>
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
