"use client";
import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { TrendingUp, MapPin, Building2 } from "lucide-react";

const FALLBACK = {
  total:8412, median_ppm2:2800, mean_ppm2:3100, top_city:"La Marsa",
  cities:[
    {city:"La Marsa",  ppm2:4800,n:892, median:4800,mean:5100},
    {city:"Hammamet",  ppm2:3900,n:1203,median:3900,mean:4100},
    {city:"Tunis",     ppm2:3200,n:2341,median:3200,mean:3400},
    {city:"Nabeul",    ppm2:2600,n:654, median:2600,mean:2800},
    {city:"Sousse",    ppm2:2800,n:1098,median:2800,mean:2950},
    {city:"Sfax",      ppm2:2100,n:876, median:2100,mean:2250},
  ],
};

export default function MarketSection() {
  const [data,setData]=useState<any>(FALLBACK);
  const [city,setCity]=useState("");
  const [propType,setPropType]=useState("");

  const load=()=>{
    fetch(`/api/market?city=${encodeURIComponent(city)}&property_type=${encodeURIComponent(propType)}`)
      .then(r=>r.ok?r.json():null).then(d=>{if(d)setData(d);}).catch(()=>{});
  };

  useEffect(()=>{load();},[]);
  const sorted=[...data.cities].sort((a,b)=>b.ppm2-a.ppm2);
  const max=sorted[0]?.ppm2??1;

  const IS={padding:"8px 12px",borderRadius:10,border:"1px solid var(--line)",background:"white",color:"var(--txt)",fontFamily:"var(--font-body)",fontSize:12,fontWeight:600} as const;

  return (
    <div style={{display:"flex",flexDirection:"column",gap:16}}>
      <div className="dash-topbar">
        <div>
          <h1>Market Overview</h1>
          <p>Price per m² and statistics by city and property type</p>
        </div>
      </div>

      {/* Filters */}
      <div style={{display:"flex",gap:10,flexWrap:"wrap",alignItems:"flex-end"}}>
        <div>
          <label style={{fontSize:10,color:"var(--mut)",display:"block",marginBottom:4,textTransform:"uppercase",letterSpacing:".06em",fontWeight:700}}>City</label>
          <input value={city} onChange={e=>setCity(e.target.value)} placeholder="All cities" style={{...IS,width:180}}/>
        </div>
        <div>
          <label style={{fontSize:10,color:"var(--mut)",display:"block",marginBottom:4,textTransform:"uppercase",letterSpacing:".06em",fontWeight:700}}>Property type</label>
          <select value={propType} onChange={e=>setPropType(e.target.value)} style={{...IS,width:160}}>
            <option value="">All types</option>
            {["apartment","villa","land","house","studio","commercial"].map(t=><option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <button className="btn-primary btn" onClick={load} style={{padding:"8px 18px",alignSelf:"flex-end"}}>Filter</button>
      </div>

      {/* KPIs */}
      <div className="kpi-grid-3">
        <div className="kpi-card">
          <div className="kpi-label">National median price</div>
          <div className="kpi-value" style={{color:"var(--navy)"}}>{data.median_ppm2?.toLocaleString("en-US")} TND/m²</div>
          <div className="kpi-sub">{data.total?.toLocaleString("en-US")} listings</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Most expensive city</div>
          <div className="kpi-value" style={{color:"var(--bad)"}}>{data.top_city}</div>
          <div className="kpi-sub">{sorted[0]?.median?.toLocaleString("en-US")} TND/m² median</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Cities covered</div>
          <div className="kpi-value" style={{color:"var(--ok)"}}>{data.cities.length}</div>
          <div className="kpi-sub">Governorates analysed</div>
        </div>
      </div>

      {/* Bar chart */}
      <div className="panel">
        <div className="panel-head"><h3>Median price per m² by city (TND)</h3></div>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={sorted} barSize={36}>
            <XAxis dataKey="city" tick={{fill:"var(--mut)",fontSize:11}} axisLine={false} tickLine={false}/>
            <YAxis tick={{fill:"var(--mut)",fontSize:10}} axisLine={false} tickLine={false} tickFormatter={v=>`${v.toLocaleString("en-US")}`}/>
            <Tooltip
              contentStyle={{background:"white",border:"1px solid var(--line)",borderRadius:10,fontSize:12}}
              formatter={(v:any)=>[`${Number(v).toLocaleString("en-US")} TND/m²`,"Median price"]}
            />
            <Bar dataKey="ppm2" fill="#2f9c7e" radius={[5,5,0,0]}/>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Detail table */}
      <div className="panel" style={{padding:0,overflow:"hidden"}}>
        <div style={{padding:"18px 20px 14px",borderBottom:"1px solid var(--line)"}}>
          <h3 style={{fontSize:15,fontWeight:700}}>Detail by city</h3>
        </div>
        <table>
          <thead>
            <tr>
              <th>City</th>
              <th>Listings</th>
              <th>Median price/m²</th>
              <th>Rank</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((c,i)=>{
              const w=c.ppm2/max*100;
              return (
                <tr key={c.city}>
                  <td style={{fontWeight:600,display:"flex",alignItems:"center",gap:5}}>
                    <MapPin size={11} color="var(--mut)"/>{c.city}
                  </td>
                  <td style={{color:"var(--mut)"}}>{c.n?.toLocaleString("en-US")} listings</td>
                  <td>
                    <div style={{display:"flex",alignItems:"center",gap:8}}>
                      <div style={{width:80,height:6,background:"var(--line)",borderRadius:3,overflow:"hidden"}}>
                        <div style={{height:"100%",width:`${w}%`,background:"var(--green)",borderRadius:3}}/>
                      </div>
                      <span style={{fontFamily:"var(--font-display)",fontWeight:700}}>{c.ppm2?.toLocaleString("en-US")} TND</span>
                    </div>
                  </td>
                  <td style={{color:i===0?"var(--bad)":"var(--mut)",fontWeight:600}}>
                    {i===0?"▲ Most expensive":`#${i+1}`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
