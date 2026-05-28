"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
  RadarChart, PolarGrid, PolarAngleAxis, Radar,
} from "recharts";
import { Map, BarChart2, Star, Layers, TrendingUp, TrendingDown, Minus, X } from "lucide-react";

// ══════════════════════════════════════════════════════════════════════════════
// DONNÉES STATIQUES
// ══════════════════════════════════════════════════════════════════════════════
const GOUVERNORATS = [
  {name:"Tunis",      lat:36.8065,lng:10.1815,ppm2:3200,listings:2341,region:"Nord-Est",   median:280000,top_type:"appartement"},
  {name:"Ariana",     lat:36.8663,lng:10.1647,ppm2:2900,listings:892, region:"Nord-Est",   median:245000,top_type:"appartement"},
  {name:"Ben Arous",  lat:36.7453,lng:10.2281,ppm2:2700,listings:654, region:"Nord-Est",   median:220000,top_type:"maison"},
  {name:"Manouba",    lat:36.8101,lng:9.7849, ppm2:2200,listings:431, region:"Nord-Est",   median:185000,top_type:"maison"},
  {name:"Nabeul",     lat:36.4513,lng:10.7357,ppm2:2600,listings:1203,region:"Nord-Est",   median:210000,top_type:"villa"},
  {name:"Zaghouan",   lat:36.4029,lng:10.1429,ppm2:1400,listings:124, region:"Nord",       median:120000,top_type:"terrain"},
  {name:"Bizerte",    lat:37.2744,lng:9.8739, ppm2:1800,listings:456, region:"Nord",       median:155000,top_type:"appartement"},
  {name:"Béja",       lat:36.7256,lng:9.1817, ppm2:1100,listings:134, region:"Nord-Ouest", median:95000, top_type:"maison"},
  {name:"Jendouba",   lat:36.5012,lng:8.7757, ppm2:900, listings:98,  region:"Nord-Ouest", median:78000, top_type:"terrain"},
  {name:"Le Kef",     lat:36.1826,lng:8.7148, ppm2:850, listings:76,  region:"Nord-Ouest", median:72000, top_type:"maison"},
  {name:"Siliana",    lat:36.0849,lng:9.3708, ppm2:780, listings:58,  region:"Nord-Ouest", median:65000, top_type:"terrain"},
  {name:"Sousse",     lat:35.8256,lng:10.6369,ppm2:2800,listings:1098,region:"Centre-Est", median:235000,top_type:"appartement"},
  {name:"Monastir",   lat:35.7643,lng:10.8113,ppm2:2600,listings:743, region:"Centre-Est", median:215000,top_type:"villa"},
  {name:"Mahdia",     lat:35.5047,lng:11.0622,ppm2:1800,listings:312, region:"Centre-Est", median:155000,top_type:"villa"},
  {name:"Sfax",       lat:34.7398,lng:10.7600,ppm2:2100,listings:876, region:"Centre-Est", median:175000,top_type:"appartement"},
  {name:"Kairouan",   lat:35.6712,lng:10.1006,ppm2:1100,listings:234, region:"Centre",     median:92000, top_type:"maison"},
  {name:"Kasserine",  lat:35.1671,lng:8.8307, ppm2:700, listings:87,  region:"Centre-Ouest",median:58000,top_type:"terrain"},
  {name:"Sidi Bouzid",lat:35.0382,lng:9.4858, ppm2:650, listings:67,  region:"Centre-Ouest",median:54000,top_type:"terrain"},
  {name:"Gabès",      lat:33.8881,lng:10.0982,ppm2:1300,listings:198, region:"Sud",        median:110000,top_type:"maison"},
  {name:"Médenine",   lat:33.3549,lng:10.5055,ppm2:1500,listings:312, region:"Sud",        median:128000,top_type:"villa"},
  {name:"Tataouine",  lat:32.9211,lng:10.4518,ppm2:600, listings:43,  region:"Sud",        median:48000, top_type:"terrain"},
  {name:"Gafsa",      lat:34.4250,lng:8.7842, ppm2:800, listings:112, region:"Sud-Ouest",  median:68000, top_type:"maison"},
  {name:"Tozeur",     lat:33.9197,lng:8.1336, ppm2:1200,listings:89,  region:"Sud-Ouest",  median:102000,top_type:"villa"},
  {name:"Kébili",     lat:33.7038,lng:8.9690, ppm2:700, listings:54,  region:"Sud-Ouest",  median:57000, top_type:"terrain"},
];

const getPpm2Color = (ppm2:number) =>
  ppm2<800?"#6B7FE8":ppm2<1500?"#6B9FE8":ppm2<2200?"#52C896":ppm2<2800?"#E8A84C":"#E05C5C";

const ZONE_COLORS = ["#C8A96E","#52C896","#7F77DD","#E05C5C","#52C8C8"];

const DEMO_SERIES: Record<string,{period:string;median_price:number}[]> = {
  "Tunis":    [{period:"2025-09",median_price:290000},{period:"2025-10",median_price:295000},{period:"2025-11",median_price:298000},{period:"2025-12",median_price:302000},{period:"2026-01",median_price:308000},{period:"2026-02",median_price:315000}],
  "Sousse":   [{period:"2025-09",median_price:225000},{period:"2025-10",median_price:230000},{period:"2025-11",median_price:228000},{period:"2025-12",median_price:235000},{period:"2026-01",median_price:242000},{period:"2026-02",median_price:248000}],
  "Hammamet": [{period:"2025-09",median_price:330000},{period:"2025-10",median_price:340000},{period:"2025-11",median_price:348000},{period:"2025-12",median_price:355000},{period:"2026-01",median_price:368000},{period:"2026-02",median_price:380000}],
  "Nabeul":   [{period:"2025-09",median_price:196000},{period:"2025-10",median_price:200000},{period:"2025-11",median_price:205000},{period:"2025-12",median_price:208000},{period:"2026-01",median_price:215000},{period:"2026-02",median_price:220000}],
  "Mahdia":   [{period:"2025-09",median_price:155000},{period:"2025-10",median_price:157000},{period:"2025-11",median_price:160000},{period:"2025-12",median_price:162000},{period:"2026-01",median_price:165000},{period:"2026-02",median_price:168000}],
  "Sfax":     [{period:"2025-09",median_price:170000},{period:"2025-10",median_price:172000},{period:"2025-11",median_price:174000},{period:"2025-12",median_price:175000},{period:"2026-01",median_price:176000},{period:"2026-02",median_price:177000}],
};

const ATTRACT: Record<string,{prix:number;croissance:number;volume:number;infrastructure:number;potentiel:number;label_prix:string;label_tendance:string}> = {
  "Tunis":    {prix:40, croissance:65,volume:95, infrastructure:95, potentiel:70, label_prix:"3 200 TND/m²",label_tendance:"↑ +8.6%"},
  "Hammamet": {prix:30, croissance:85,volume:72, infrastructure:78, potentiel:90, label_prix:"3 800 TND/m²",label_tendance:"↑ +15.2%"},
  "Nabeul":   {prix:55, croissance:75,volume:80, infrastructure:72, potentiel:85, label_prix:"2 600 TND/m²",label_tendance:"↑ +12.2%"},
  "Sousse":   {prix:45, croissance:70,volume:85, infrastructure:82, potentiel:80, label_prix:"2 800 TND/m²",label_tendance:"↑ +10.2%"},
  "Monastir": {prix:48, croissance:62,volume:74, infrastructure:80, potentiel:75, label_prix:"2 600 TND/m²",label_tendance:"↑ +8.1%"},
  "Sfax":     {prix:62, croissance:40,volume:78, infrastructure:80, potentiel:60, label_prix:"2 100 TND/m²",label_tendance:"→ +4.1%"},
  "Mahdia":   {prix:72, croissance:68,volume:52, infrastructure:58, potentiel:82, label_prix:"1 800 TND/m²",label_tendance:"↑ +8.4%"},
  "Bizerte":  {prix:68, croissance:45,volume:58, infrastructure:68, potentiel:65, label_prix:"1 800 TND/m²",label_tendance:"↑ +5.5%"},
  "Kasserine":{prix:90, croissance:20,volume:25, infrastructure:35, potentiel:30, label_prix:"700 TND/m²", label_tendance:"↓ -9.3%"},
};
const ATTRACT_ZONES = Object.keys(ATTRACT);
const AXES = ["prix","croissance","volume","infrastructure","potentiel"];

// ══════════════════════════════════════════════════════════════════════════════
// UTILITAIRES
// ══════════════════════════════════════════════════════════════════════════════
const loadScript = (src:string):Promise<void> => new Promise((res,rej)=>{
  if(document.querySelector(`script[src="${src}"]`)){res();return;}
  const s=document.createElement("script");s.src=src;s.async=true;
  s.onload=()=>res(); s.onerror=()=>rej(); document.head.appendChild(s);
});
const loadLink = (href:string) => {
  if(document.querySelector(`link[href="${href}"]`)) return;
  const l=document.createElement("link");l.rel="stylesheet";l.href=href;
  document.head.appendChild(l);
};

// ══════════════════════════════════════════════════════════════════════════════
// COMPOSANT CARTE (INLINE)
// ══════════════════════════════════════════════════════════════════════════════
function CarteMap({layerMode}:{layerMode:"circles"|"heatmap"|"clusters"}) {
  const mapRef  = useRef<HTMLDivElement>(null);
  const mapObj  = useRef<any>(null);
  const layers  = useRef<any[]>([]);
  const [ready, setReady] = useState(false);

  // Init Leaflet une seule fois
  useEffect(()=>{
    if(mapObj.current || !mapRef.current) return;
    loadLink("https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css");
    loadScript("https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js")
      .then(()=>{
        const L=(window as any).L;
        const map = L.map(mapRef.current,{center:[34.5,9.0],zoom:6,zoomControl:true});
        L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",{
          attribution:"© OSM © CARTO",maxZoom:19,
        }).addTo(map);
        // Badge démo
        const ctrl = L.control({position:"topright"});
        ctrl.onAdd=()=>{const d=document.createElement("div");d.innerHTML='<span style="background:#C8A96E;color:#18181C;font-size:10px;padding:3px 8px;border-radius:4px;font-weight:600;letter-spacing:.05em">● DONNÉES DÉMO</span>';return d;};
        ctrl.addTo(map);
        mapObj.current=map;
        setReady(true);
      }).catch(()=>{});
  },[]);

  // Changer la couche
  useEffect(()=>{
    if(!ready||!mapObj.current) return;
    const L=(window as any).L;
    const map=mapObj.current;

    // Nettoie toutes les couches précédentes
    layers.current.forEach(l=>{try{map.removeLayer(l);}catch{}});
    layers.current=[];

    if(layerMode==="circles") {
      // Cercles proportionnels colorés
      GOUVERNORATS.forEach(g=>{
        const r=Math.sqrt(g.listings)*300;
        const c=getPpm2Color(g.ppm2);
        const circle=L.circle([g.lat,g.lng],{
          radius:r, color:c, fillColor:c, fillOpacity:.4, weight:1.5,
        }).addTo(map);
        const label=L.divIcon({html:`<div style="font-family:sans-serif;text-align:center;pointer-events:none"><div style="font-size:11px;font-weight:600;color:#F2F0EC;text-shadow:0 0 4px #000">${g.name}</div><div style="font-size:10px;color:${c};text-shadow:0 0 4px #000">${g.ppm2.toLocaleString("fr-FR")} TND</div></div>`,
          iconSize:[120,32],iconAnchor:[60,16],className:""});
        const marker=L.marker([g.lat,g.lng],{icon:label}).addTo(map);
        const popup=`<div style="font-family:sans-serif;min-width:200px;color:#F2F0EC">
          <div style="font-size:14px;font-weight:600;border-bottom:1px solid rgba(255,255,255,.1);padding-bottom:8px;margin-bottom:8px">📍 ${g.name} <span style="font-size:10px;color:#6B6966">${g.region}</span></div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">
            <div style="background:rgba(255,255,255,.06);border-radius:6px;padding:8px"><div style="font-size:9px;color:#6B6966">PRIX/M²</div><div style="font-size:15px;font-weight:700;color:${c}">${g.ppm2.toLocaleString("fr-FR")} TND</div></div>
            <div style="background:rgba(255,255,255,.06);border-radius:6px;padding:8px"><div style="font-size:9px;color:#6B6966">ANNONCES</div><div style="font-size:15px;font-weight:700">${g.listings.toLocaleString("fr-FR")}</div></div>
          </div>
          <div style="font-size:11px;color:#6B6966">Médian : <b style="color:#C8A96E">${g.median.toLocaleString("fr-FR")} TND</b> · Top : <b style="color:#F2F0EC">${g.top_type}</b></div>
        </div>`;
        circle.bindPopup(popup,{className:"em-popup",maxWidth:240});
        layers.current.push(circle,marker);
      });
    }

    else if(layerMode==="heatmap") {
      // Données heatmap depuis les gouvernorats
      const maxPpm2 = Math.max(...GOUVERNORATS.map(g=>g.ppm2));
      loadScript("https://cdnjs.cloudflare.com/ajax/libs/Leaflet.heat/0.2.0/leaflet-heat.js")
        .then(()=>{
          const L2=(window as any).L;
          if(!L2.heatLayer){
            // Fallback si plugin ne charge pas : circles colorés
            GOUVERNORATS.forEach(g=>{
              const c=getPpm2Color(g.ppm2);
              const m=L.circleMarker([g.lat,g.lng],{radius:14+g.ppm2/300,color:c,fillColor:c,fillOpacity:.7,weight:0}).addTo(map);
              m.bindPopup(`<b>${g.name}</b><br/>${g.ppm2.toLocaleString("fr-FR")} TND/m²`);
              layers.current.push(m);
            });
            return;
          }
          // Points heatmap générés depuis les gouvernorats (intensité = ppm2 normalisé)
          const pts = GOUVERNORATS.map(g=>[g.lat,g.lng, g.ppm2/maxPpm2]);
          // Ajoute du bruit autour de chaque gouvernorat pour un rendu naturel
          const noisePts:number[][] = [];
          GOUVERNORATS.forEach(g=>{
            const count = Math.floor(g.listings/50);
            for(let i=0;i<count;i++){
              const dlat=(Math.random()-.5)*.8;
              const dlng=(Math.random()-.5)*.8;
              noisePts.push([g.lat+dlat, g.lng+dlng, (g.ppm2/maxPpm2)*(.5+Math.random()*.5)]);
            }
          });
          const heat=L2.heatLayer([...pts,...noisePts],{
            radius:40, blur:30, maxZoom:10,
            gradient:{.2:"#4287f5",.4:"#52C896",.65:"#E8A84C",.85:"orange",1:"#E05C5C"},
          }).addTo(map);
          layers.current.push(heat);
        }).catch(()=>{
          // Fallback si réseau bloqué
          GOUVERNORATS.forEach(g=>{
            const c=getPpm2Color(g.ppm2);
            const m=L.circle([g.lat,g.lng],{radius:g.ppm2*50,color:c,fillColor:c,fillOpacity:.3,weight:0}).addTo(map);
            layers.current.push(m);
          });
        });
    }

    else if(layerMode==="clusters") {
      loadLink("https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.css");
      loadLink("https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.Default.css");
      loadScript("https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/leaflet.markercluster.js")
        .then(()=>{
          const L2=(window as any).L;
          if(!L2.markerClusterGroup){
            // Fallback : markers simples
            GOUVERNORATS.forEach(g=>{
              const c=getPpm2Color(g.ppm2);
              const m=L.circleMarker([g.lat,g.lng],{radius:8,color:c,fillColor:c,fillOpacity:.85,weight:2}).addTo(map);
              m.bindPopup(`<b>${g.name}</b><br/>${g.listings} annonces · ${g.ppm2} TND/m²`);
              layers.current.push(m);
            });
            return;
          }
          const group=L2.markerClusterGroup({
            maxClusterRadius:60,showCoverageOnHover:false,
            iconCreateFunction:(cluster:any)=>{
              const count=cluster.getChildCount();
              const col=count>100?"#E05C5C":count>30?"#E8A84C":"#52C896";
              return L2.divIcon({html:`<div style="background:${col};color:#18181C;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;border:2px solid rgba(255,255,255,.3)">${count}</div>`,iconSize:[36,36],className:""});
            },
          });
          // Ajoute les gouvernorats comme markers individuels
          GOUVERNORATS.forEach(g=>{
            const c=getPpm2Color(g.ppm2);
            // Simule plusieurs annonces par gouvernorat
            const count=Math.min(Math.floor(g.listings/30),20);
            for(let i=0;i<count;i++){
              const dlat=(Math.random()-.5)*.4;
              const dlng=(Math.random()-.5)*.4;
              const icon=L2.divIcon({html:`<div style="background:${c};width:10px;height:10px;border-radius:50%;border:1px solid rgba(255,255,255,.4)"></div>`,iconSize:[10,10],className:""});
              const m=L2.marker([g.lat+dlat,g.lng+dlng],{icon});
              m.bindPopup(`<b>${g.name}</b><br/>${g.ppm2.toLocaleString("fr-FR")} TND/m²<br/>${g.listings} annonces`);
              group.addLayer(m);
            }
          });
          map.addLayer(group);
          layers.current.push(group);
        }).catch(()=>{
          GOUVERNORATS.forEach(g=>{
            const c=getPpm2Color(g.ppm2);
            const m=L.circleMarker([g.lat,g.lng],{radius:8,color:c,fillColor:c,fillOpacity:.85,weight:2}).addTo(map);
            layers.current.push(m);
          });
        });
    }
  },[ready,layerMode]);

  return (
    <div ref={mapRef} style={{
      height:580, width:"100%",
      borderRadius:10, overflow:"hidden",
      background:"var(--el)",
    }}/>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// COMPARATEUR DE ZONES (INLINE)
// ══════════════════════════════════════════════════════════════════════════════
function ZoneComparator() {
  const [zones,  setZones]  = useState(["Tunis","Sousse","Hammamet"]);
  const [metric, setMetric] = useState<"price"|"volume">("price");

  const addZone  = (z:string) => { if(!zones.includes(z)&&zones.length<5) setZones(p=>[...p,z]); };
  const rmZone   = (z:string) => { if(zones.length>1) setZones(p=>p.filter(x=>x!==z)); };
  const available= Object.keys(DEMO_SERIES).filter(z=>!zones.includes(z));

  // Fusionne les séries
  const periods = [...new Set(zones.flatMap(z=>DEMO_SERIES[z]?.map(p=>p.period)||[]))].sort();
  const chartData = periods.map(period=>{
    const row:any={period};
    zones.forEach(z=>{const pt=DEMO_SERIES[z]?.find(p=>p.period===period);if(pt) row[z]=pt.median_price;});
    return row;
  });

  const trend = (z:string) => {
    const pts=DEMO_SERIES[z]||[];
    if(pts.length<2) return 0;
    return (pts[pts.length-1].median_price-pts[0].median_price)/pts[0].median_price*100;
  };

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:14 }}>
      {/* Sélecteur */}
      <div style={{ display:"flex", gap:6, flexWrap:"wrap", alignItems:"center" }}>
        {zones.map((z,i)=>(
          <div key={z} style={{ display:"flex",alignItems:"center",gap:5,padding:"4px 10px",borderRadius:999,background:`${ZONE_COLORS[i]}18`,border:`1px solid ${ZONE_COLORS[i]}40` }}>
            <div style={{ width:6,height:6,borderRadius:"50%",background:ZONE_COLORS[i] }}/>
            <span style={{ fontSize:11,color:ZONE_COLORS[i],fontWeight:500 }}>{z}</span>
            <button onClick={()=>rmZone(z)} style={{ background:"none",border:"none",cursor:"pointer",color:ZONE_COLORS[i],padding:0 }}><X size={10}/></button>
          </div>
        ))}
        {zones.length<5&&available.length>0&&(
          <select value="" onChange={e=>e.target.value&&addZone(e.target.value)} style={{ padding:"4px 10px",borderRadius:999,fontSize:11,border:"1px dashed var(--bor)",background:"var(--el)",color:"var(--mut)",cursor:"pointer" }}>
            <option value="">+ Ajouter</option>
            {available.map(z=><option key={z} value={z}>{z}</option>)}
          </select>
        )}
        <div style={{ marginLeft:"auto",display:"flex",gap:3,background:"var(--el)",padding:3,borderRadius:7,border:"1px solid var(--bor)" }}>
          {["price","volume"].map(m=>(
            <button key={m} onClick={()=>setMetric(m as any)} style={{ padding:"4px 10px",borderRadius:5,border:"none",background:metric===m?"var(--card)":"transparent",color:metric===m?"var(--gold)":"var(--mut)",fontSize:11,fontFamily:"var(--font-body)",cursor:"pointer" }}>{m==="price"?"Prix":"Volume"}</button>
          ))}
        </div>
      </div>

      {/* Graphique */}
      <div style={{ background:"var(--card)",border:"1px solid var(--bor)",borderRadius:12,padding:20 }}>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={chartData}>
            <XAxis dataKey="period" tick={{fontSize:10,fill:"var(--mut)"}} axisLine={false} tickLine={false}/>
            <YAxis tick={{fontSize:10,fill:"var(--mut)"}} axisLine={false} tickLine={false} tickFormatter={v=>`${(v/1000).toFixed(0)}K`}/>
            <Tooltip contentStyle={{background:"var(--card)",border:"1px solid var(--bor)",borderRadius:8,fontSize:11}} formatter={(v:number,n:string)=>[`${v?.toLocaleString("fr-TN")} TND`,n]}/>
            <Legend wrapperStyle={{fontSize:11}}/>
            {zones.map((z,i)=><Line key={z} type="monotone" dataKey={z} stroke={ZONE_COLORS[i]} strokeWidth={2} dot={false} activeDot={{r:4}}/>)}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Scorecard */}
      <div style={{ display:"grid",gridTemplateColumns:`repeat(${zones.length},1fr)`,gap:10 }}>
        {zones.map((z,i)=>{
          const t=trend(z); const pts=DEMO_SERIES[z]||[];
          const last=pts[pts.length-1]?.median_price;
          const c=ZONE_COLORS[i];
          return (
            <div key={z} style={{ background:`${c}08`,border:`1px solid ${c}22`,borderRadius:8,padding:"10px 12px",textAlign:"center" }}>
              <div style={{ fontSize:10,color:"var(--mut)",marginBottom:4 }}>{z}</div>
              {last&&<div style={{ fontFamily:"var(--font-display)",fontSize:14,fontWeight:600,color:c,marginBottom:3 }}>{(last/1000).toFixed(0)}K TND</div>}
              <div style={{ display:"flex",alignItems:"center",justifyContent:"center",gap:3 }}>
                {t>0?<TrendingUp size={10} color="#52C896"/>:t<0?<TrendingDown size={10} color="#E05C5C"/>:<Minus size={10} color="var(--mut)"/>}
                <span style={{ fontSize:11,fontWeight:600,color:t>0?"#52C896":t<0?"#E05C5C":"var(--mut)" }}>{t>0?"+":""}{t.toFixed(1)}%</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// RADAR D'ATTRACTIVITÉ (INLINE)
// ══════════════════════════════════════════════════════════════════════════════
function RadarAttract() {
  const [zone1, setZone1] = useState("Hammamet");
  const [zone2, setZone2] = useState("Mahdia");
  const [cmp,   setCmp]   = useState(true);

  const zones = cmp?[zone1,zone2]:[zone1];
  const d1=ATTRACT[zone1]; const d2=ATTRACT[zone2];
  const score=(z:string)=>Math.round(AXES.reduce((s,k)=>s+(ATTRACT[z]?.[k as keyof typeof d1] as number||0),0)/AXES.length);

  const radarData = AXES.map(key=>{
    const row:any={axis:key};
    zones.forEach(z=>{row[z]=ATTRACT[z]?.[key as keyof typeof d1]??0;});
    return row;
  });

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
      {/* Sélecteurs */}
      <div style={{ display:"flex",gap:10,alignItems:"center" }}>
        <select value={zone1} onChange={e=>setZone1(e.target.value)} style={{ flex:1,padding:"7px 10px",borderRadius:7,fontSize:12,border:"1px solid rgba(200,169,110,.4)",background:"rgba(200,169,110,.08)",color:"#C8A96E" }}>
          {ATTRACT_ZONES.map(z=><option key={z} value={z}>{z}</option>)}
        </select>
        {cmp&&<>
          <span style={{ color:"var(--mut)",fontSize:11 }}>vs</span>
          <select value={zone2} onChange={e=>setZone2(e.target.value)} style={{ flex:1,padding:"7px 10px",borderRadius:7,fontSize:12,border:"1px solid rgba(82,200,150,.4)",background:"rgba(82,200,150,.08)",color:"#52C896" }}>
            {ATTRACT_ZONES.filter(z=>z!==zone1).map(z=><option key={z} value={z}>{z}</option>)}
          </select>
        </>}
        <button onClick={()=>setCmp(c=>!c)} style={{ padding:"6px 12px",borderRadius:6,fontSize:11,border:"1px solid var(--bor)",background:cmp?"var(--gdim)":"transparent",color:cmp?"var(--gold)":"var(--mut)",cursor:"pointer",fontFamily:"var(--font-body)",flexShrink:0 }}>
          {cmp?"Comparaison":"Zone unique"}
        </button>
      </div>

      {/* Radar */}
      <div style={{ background:"var(--card)",border:"1px solid var(--bor)",borderRadius:12,padding:20 }}>
        <ResponsiveContainer width="100%" height={280}>
          <RadarChart data={radarData} margin={{top:10,right:30,bottom:10,left:30}}>
            <PolarGrid stroke="rgba(255,255,255,.08)"/>
            <PolarAngleAxis dataKey="axis" tick={{fill:"rgba(242,240,236,.6)",fontSize:11}}/>
            <Radar name={zone1} dataKey={zone1} stroke="#C8A96E" fill="#C8A96E" fillOpacity={.25} strokeWidth={2}/>
            {cmp&&<Radar name={zone2} dataKey={zone2} stroke="#52C896" fill="#52C896" fillOpacity={.18} strokeWidth={2} strokeDasharray="5 3"/>}
            <Tooltip contentStyle={{background:"var(--card)",border:"1px solid var(--bor)",borderRadius:8,fontSize:11}} formatter={(v:number,n:string)=>[`${v}/100`,n]}/>
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* Scores */}
      <div style={{ display:"grid",gridTemplateColumns:cmp?"1fr 1fr":"1fr",gap:14 }}>
        {[zone1,...(cmp?[zone2]:[])].map((z,i)=>{
          const d=ATTRACT[z]; if(!d) return null;
          const col=i===0?"#C8A96E":"#52C896";
          const sc=score(z);
          return (
            <div key={z} style={{ background:`${col}08`,border:`1px solid ${col}22`,borderRadius:10,padding:"16px 18px",textAlign:"center" }}>
              <div style={{ fontSize:13,fontWeight:600,color:col,marginBottom:12 }}>{z}</div>
              <div style={{ display:"grid",gridTemplateColumns:"1fr 1fr",gap:8,marginBottom:12 }}>
                {AXES.slice(0,4).map(k=>(
                  <div key={k}>
                    <div style={{ fontFamily:"var(--font-display)",fontSize:18,fontWeight:700,color:col }}>{d[k as keyof typeof d] as number}</div>
                    <div style={{ height:3,background:"var(--el)",borderRadius:2,marginTop:3,overflow:"hidden" }}>
                      <div style={{ height:"100%",width:`${d[k as keyof typeof d] as number}%`,background:col,borderRadius:2 }}/>
                    </div>
                    <div style={{ fontSize:9,color:"var(--mut)",marginTop:3,textTransform:"uppercase" }}>{k}</div>
                  </div>
                ))}
              </div>
              <div style={{ fontSize:11,color:col,marginBottom:8 }}>{d.label_tendance} · {d.label_prix}</div>
              <div style={{ fontFamily:"var(--font-display)",fontSize:30,fontWeight:700,color:col }}>{sc}</div>
              <div style={{ fontSize:10,color:"var(--mut)" }}>score / 100</div>
            </div>
          );
        })}
      </div>

      {/* Verdict */}
      {cmp&&score(zone1)!==score(zone2)&&(
        <div style={{ padding:"10px 14px",borderRadius:8,textAlign:"center",fontSize:12,background:score(zone1)>score(zone2)?"rgba(200,169,110,.08)":"rgba(82,200,150,.08)",border:`1px solid ${score(zone1)>score(zone2)?"rgba(200,169,110,.3)":"rgba(82,200,150,.3)"}`,color:score(zone1)>score(zone2)?"#C8A96E":"#52C896" }}>
          {score(zone1)>score(zone2)
            ?`${zone1} est plus attractif (+${score(zone1)-score(zone2)} pts)`
            :`${zone2} est plus attractif (+${score(zone2)-score(zone1)} pts)`}
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// PAGE PRINCIPALE
// ══════════════════════════════════════════════════════════════════════════════
type TabId = "carte"|"comparateur"|"radar";

export default function CartePage() {
  const [tab,       setTab]       = useState<TabId>("carte");
  const [layerMode, setLayerMode] = useState<"circles"|"heatmap"|"clusters">("circles");

  const TABS = [
    {id:"carte"      as TabId,label:"Carte interactive",    Icon:Map},
    {id:"comparateur"as TabId,label:"Comparateur de zones", Icon:BarChart2},
    {id:"radar"      as TabId,label:"Radar d'attractivité", Icon:Star},
  ];

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:20 }}>
      {/* Popup styles */}
      <style>{`.leaflet-popup-content-wrapper{background:#18181C!important;border:1px solid rgba(255,255,255,.1)!important;border-radius:10px!important;color:#F2F0EC!important;box-shadow:0 8px 32px rgba(0,0,0,.6)!important}.leaflet-popup-tip{background:#18181C!important}.leaflet-popup-close-button{color:#6B6966!important}`}</style>

      <div>
        <h1 style={{ fontFamily:"var(--font-display)",fontSize:22,fontWeight:600,marginBottom:4 }}>Carte du marché</h1>
        <p style={{ fontSize:13,color:"var(--mut)" }}>Visualisation spatiale · Comparateur de zones · Radar d'attractivité</p>
      </div>

      {/* Onglets */}
      <div style={{ display:"flex",gap:4,background:"var(--el)",padding:4,borderRadius:10,border:"1px solid var(--bor)" }}>
        {TABS.map(({id,label,Icon})=>(
          <button key={id} onClick={()=>setTab(id)} style={{ flex:1,display:"flex",alignItems:"center",justifyContent:"center",gap:6,padding:"8px 12px",borderRadius:7,border:"none",cursor:"pointer",fontSize:12,fontFamily:"var(--font-body)",background:tab===id?"var(--card)":"transparent",color:tab===id?"var(--gold)":"var(--mut)",fontWeight:tab===id?500:400,transition:"all .15s" }}>
            <Icon size={12}/>{label}
          </button>
        ))}
      </div>

      {/* ── Carte ── */}
      {tab==="carte"&&(
        <div style={{ display:"flex",flexDirection:"column",gap:14 }}>
          {/* Sélecteur couche */}
          <div style={{ display:"flex",gap:8,alignItems:"center" }}>
            <Layers size={13} color="var(--mut)"/>
            <span style={{ fontSize:12,color:"var(--mut)" }}>Couche :</span>
            {([["circles","🔵 Cercles"],["heatmap","🌡️ Heatmap"],["clusters","🔗 Clusters"]] as const).map(([m,l])=>(
              <button key={m} onClick={()=>setLayerMode(m)} style={{ padding:"4px 12px",borderRadius:6,border:"none",cursor:"pointer",fontSize:11,fontFamily:"var(--font-body)",background:layerMode===m?"var(--gdim)":"var(--el)",color:layerMode===m?"var(--gold)":"var(--mut)",border:layerMode===m?"1px solid var(--gbor)":"1px solid var(--bor)" as any }}>
                {l}
              </button>
            ))}
          </div>

          {/* Légende heatmap */}
          {layerMode==="heatmap"&&(
            <div style={{ background:"var(--card)",border:"1px solid var(--bor)",borderRadius:10,padding:"12px 16px" }}>
              <div style={{ fontSize:11,fontWeight:500,marginBottom:8 }}>Légende — Prix/m² (TND)</div>
              <div style={{ display:"flex",alignItems:"center",gap:12 }}>
                <div style={{ flex:1,height:8,borderRadius:4,background:"linear-gradient(to right,#4287f5,#52C896,#E8A84C,orange,#E05C5C)" }}/>
                <div style={{ display:"flex",gap:16,fontSize:10,color:"var(--mut)",flexShrink:0 }}>
                  <span>Bas (&lt;1 500)</span><span>Médian (~2 200)</span><span>Élevé (&gt;3 500)</span>
                </div>
              </div>
            </div>
          )}

          {/* Légende clusters */}
          {layerMode==="clusters"&&(
            <div style={{ background:"var(--card)",border:"1px solid var(--bor)",borderRadius:10,padding:"12px 16px",fontSize:11,color:"var(--mut)" }}>
              🔗 <b style={{ color:"var(--txt)" }}>Mode Clusters</b> — Les annonces sont regroupées par proximité géographique. Chaque bulle colorée indique le nombre d'annonces dans la zone. Zoomez pour voir les annonces individuelles. Couleur : <span style={{ color:"#52C896" }}>vert</span> = peu d'annonces · <span style={{ color:"#E8A84C" }}>orange</span> = moyen · <span style={{ color:"#E05C5C" }}>rouge</span> = dense.
            </div>
          )}

          {/* La carte */}
          <CarteMap layerMode={layerMode}/>

          {/* Stats */}
          <div style={{ display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:12 }}>
            {[
              {label:"Gouvernorats",  val:"24"},
              {label:"Prix/m² médian",val:"2 100 TND"},
              {label:"Annonces",      val:GOUVERNORATS.reduce((s,g)=>s+g.listings,0).toLocaleString("fr-TN")},
              {label:"Zone la + chère",val:GOUVERNORATS.slice().sort((a,b)=>b.ppm2-a.ppm2)[0].name},
            ].map(k=>(
              <div key={k.label} style={{ background:"var(--card)",border:"1px solid var(--bor)",borderRadius:10,padding:"14px 16px" }}>
                <div style={{ fontFamily:"var(--font-display)",fontSize:20,fontWeight:600,color:"var(--gold)" }}>{k.val}</div>
                <div style={{ fontSize:11,color:"var(--mut)",marginTop:3 }}>{k.label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Comparateur ── */}
      {tab==="comparateur"&&<ZoneComparator/>}

      {/* ── Radar ── */}
      {tab==="radar"&&<RadarAttract/>}
    </div>
  );
}
