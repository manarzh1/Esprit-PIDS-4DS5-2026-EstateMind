"use client";
import { useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { Gauge } from "@/components/Gauge";
import { Badge } from "@/components/Badge";
import { analyzeListing } from "@/lib/api";
import type { AnalyzeResult, Verdict } from "@/types";

const TC = (s:number) => s>=.75?"var(--ok)":s>=.5?"var(--warn)":"var(--bad)";
const LC = (s:number) => s<.3?"var(--ok)":s<.6?"var(--warn)":"var(--bad)";

const VERDICT_BG:Record<Verdict,string> = {
  FAVORABLE:"rgba(35,135,101,.08)",
  ATTENTION:"rgba(191,118,24,.08)",
  DANGER:"rgba(204,59,37,.08)",
};
const VERDICT_BORDER:Record<Verdict,string> = {
  FAVORABLE:"rgba(35,135,101,.28)",
  ATTENTION:"rgba(191,118,24,.28)",
  DANGER:"rgba(204,59,37,.28)",
};

const PROPERTY_TYPES = ["apartment","villa","house","land","studio","commercial","building","farm"];
const SOURCES = ["private","tayara","mubawab","remax","tecnocasa","century21","darkom"];

const IS = {
  padding:"9px 12px", borderRadius:10, border:"1px solid var(--line)",
  background:"white", color:"var(--txt)", fontFamily:"var(--font-body)",
  fontSize:13, fontWeight:600, width:"100%", outline:"none",
} as const;

export default function BO3Page() {
  const [form,setForm]=useState({
    description:"",price:"",surface:"",city:"",
    property_type:"apartment",source:"private",
  });
  const [loading,setLoading]=useState(false);
  const [result,setResult]=useState<AnalyzeResult|null>(null);
  const [error,setError]=useState<string|null>(null);

  const up=(k:string,v:string)=>setForm(f=>({...f,[k]:v}));
  const canSubmit=!loading&&Boolean(form.description)&&Boolean(form.price)&&Boolean(form.city);

  const analyze=async()=>{
    setLoading(true);setResult(null);setError(null);
    try{
      const data=await analyzeListing({
        description:form.description,
        price:Number(form.price),
        surface:Number(form.surface)||0,
        city:form.city,
        property_type:form.property_type,
        source:form.source,
      });
      setResult(data);
    } catch(e:unknown){
      setError(e instanceof Error?e.message:"Analysis error. Check that the backend is running.");
    }
    setLoading(false);
  };

  return (
    <div style={{display:"flex",flexDirection:"column",gap:16}}>
      {/* Header */}
      <div style={{display:"flex",alignItems:"center",gap:10}}>
        <span style={{display:"inline-block",background:"var(--mint)",color:"var(--green)",borderRadius:999,padding:"6px 14px",fontSize:11,fontWeight:800,textTransform:"uppercase",letterSpacing:".07em"}}>BO3</span>
        <span style={{fontSize:13,color:"var(--mut)",fontWeight:600}}>Price Estimation — Trust Score · Legal Risk · AI Analysis</span>
      </div>

      <div className="dash-topbar">
        <div>
          <h1>Analyse a Listing</h1>
          <p>AI trust score evaluation + legal risk via Random Forest & NLP</p>
        </div>
      </div>

      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:20,alignItems:"start"}}>
        {/* Form */}
        <div className="panel">
          <div style={{fontSize:16,fontWeight:700,marginBottom:20,color:"var(--navy)"}}>Listing information</div>
          <div style={{display:"flex",flexDirection:"column",gap:14}}>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
              <div>
                <label style={{fontSize:10,color:"var(--mut)",textTransform:"uppercase",letterSpacing:".06em",display:"block",marginBottom:5,fontWeight:700}}>Property type</label>
                <select value={form.property_type} onChange={e=>up("property_type",e.target.value)} style={IS}>
                  {PROPERTY_TYPES.map(t=><option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label style={{fontSize:10,color:"var(--mut)",textTransform:"uppercase",letterSpacing:".06em",display:"block",marginBottom:5,fontWeight:700}}>City</label>
                <input value={form.city} onChange={e=>up("city",e.target.value)} placeholder="e.g. Tunis, Hammamet..." style={IS}/>
              </div>
            </div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
              <div>
                <label style={{fontSize:10,color:"var(--mut)",textTransform:"uppercase",letterSpacing:".06em",display:"block",marginBottom:5,fontWeight:700}}>Price (TND)</label>
                <input type="number" value={form.price} onChange={e=>up("price",e.target.value)} placeholder="e.g. 280000" style={IS}/>
              </div>
              <div>
                <label style={{fontSize:10,color:"var(--mut)",textTransform:"uppercase",letterSpacing:".06em",display:"block",marginBottom:5,fontWeight:700}}>Surface (m²)</label>
                <input type="number" value={form.surface} onChange={e=>up("surface",e.target.value)} placeholder="e.g. 120" style={IS}/>
              </div>
            </div>
            <div>
              <label style={{fontSize:10,color:"var(--mut)",textTransform:"uppercase",letterSpacing:".06em",display:"block",marginBottom:5,fontWeight:700}}>Source</label>
              <select value={form.source} onChange={e=>up("source",e.target.value)} style={IS}>
                {SOURCES.map(s=><option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label style={{fontSize:10,color:"var(--mut)",textTransform:"uppercase",letterSpacing:".06em",display:"block",marginBottom:5,fontWeight:700}}>Listing description</label>
              <textarea value={form.description} onChange={e=>up("description",e.target.value)}
                placeholder="Paste the full listing text here..."
                rows={6}
                style={{...IS,resize:"vertical",lineHeight:1.7}}/>
            </div>
            <button className="btn-primary btn" onClick={analyze} disabled={!canSubmit} style={{padding:"12px",fontSize:13,justifyContent:"center"}}>
              {loading
                ? <><Loader2 size={14} style={{animation:"spin 1s linear infinite"}}/> Analysing...</>
                : <><Sparkles size={14}/> Analyse this listing</>
              }
            </button>
          </div>
        </div>

        {/* Results */}
        <div>
          {!result&&!loading&&(
            <div className="panel" style={{padding:48,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",gap:16,minHeight:420,textAlign:"center"}}>
              <div style={{width:52,height:52,borderRadius:13,background:"var(--mint)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:22}}>🔍</div>
              <div>
                <div style={{fontSize:16,fontWeight:700,marginBottom:8}}>Fill in the form</div>
                <div style={{fontSize:13,color:"var(--mut)",lineHeight:1.6}}>
                  AI will analyse the trust score,<br/>legal risk and alert signals.
                </div>
              </div>
            </div>
          )}

          {loading&&(
            <div className="panel" style={{padding:48,display:"flex",flexDirection:"column",alignItems:"center",gap:20,minHeight:420,justifyContent:"center"}}>
              <div style={{width:48,height:48,border:"3px solid var(--line)",borderTop:"3px solid var(--green)",borderRadius:"50%",animation:"spin 1s linear infinite"}}/>
              <div style={{fontSize:13,color:"var(--mut)"}}>Analysing...</div>
            </div>
          )}

          {error&&(
            <div style={{background:"rgba(204,59,37,.08)",border:"1px solid rgba(204,59,37,.25)",borderRadius:12,padding:16,fontSize:13,color:"var(--bad)",marginBottom:14}}>
              {error}
            </div>
          )}

          {result&&(
            <div style={{display:"flex",flexDirection:"column",gap:14}}>
              {/* Verdict */}
              <div style={{background:VERDICT_BG[result.verdict],border:`1px solid ${VERDICT_BORDER[result.verdict]}`,borderRadius:12,padding:"16px 22px",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
                <span style={{fontSize:15,fontWeight:700}}>Final verdict</span>
                <Badge level={result.verdict}/>
              </div>

              {/* Gauges */}
              <div className="panel" style={{display:"flex",justifyContent:"space-around",alignItems:"center",padding:22}}>
                <Gauge score={result.trust_score} label="Trust Score" color={TC(result.trust_score)}/>
                <div style={{width:1,height:72,background:"var(--line)"}}/>
                <Gauge score={1-result.legal_risk_score} label="Legal Security" color={LC(result.legal_risk_score)}/>
              </div>

              {/* Alert flags */}
              {[...(result.fraud_flags??[]),...(result.legal_flags??[])].length>0&&(
                <div className="panel" style={{padding:20}}>
                  <div style={{fontSize:12,fontWeight:700,textTransform:"uppercase",letterSpacing:".06em",color:"var(--bad)",marginBottom:12}}>Alert signals</div>
                  {[...(result.fraud_flags??[]),...(result.legal_flags??[])].map((f,i)=>(
                    <div key={i} style={{display:"flex",alignItems:"flex-start",gap:9,padding:"8px 0",borderBottom:"1px solid var(--line)"}}>
                      <span style={{fontSize:14,marginTop:1}}>⚠</span>
                      <span style={{fontSize:13,lineHeight:1.5}}>{f}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Applicable laws */}
              {result.relevant_laws?.length>0&&(
                <div className="panel" style={{padding:20}}>
                  <div style={{fontSize:12,fontWeight:700,textTransform:"uppercase",letterSpacing:".06em",color:"var(--navy)",marginBottom:14}}>Applicable laws</div>
                  {result.relevant_laws.map((l,i)=>(
                    <div key={i} style={{borderLeft:"2px solid rgba(47,156,126,.5)",paddingLeft:13,marginBottom:12}}>
                      <div style={{fontSize:11,color:"var(--green)",marginBottom:3,fontWeight:700}}>{l.article} — {l.source}</div>
                      <div style={{fontSize:12,color:"var(--mut)",lineHeight:1.5}}>{l.summary}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Price analysis */}
              <div style={{background:"rgba(74,111,165,.08)",border:"1px solid rgba(74,111,165,.22)",borderRadius:10,padding:"13px 16px"}}>
                <div style={{fontSize:10,color:"var(--info)",textTransform:"uppercase",letterSpacing:".06em",marginBottom:4,fontWeight:700}}>Price analysis</div>
                <div style={{fontSize:13,lineHeight:1.5}}>{result.price_analysis}</div>
              </div>

              {/* Recommendation */}
              <div style={{background:"rgba(47,156,126,.07)",border:"1px solid rgba(47,156,126,.25)",borderRadius:10,padding:"14px 18px"}}>
                <div style={{fontSize:10,color:"var(--green)",textTransform:"uppercase",letterSpacing:".06em",marginBottom:6,fontWeight:700}}>Recommendation</div>
                <div style={{fontSize:13,lineHeight:1.6}}>{result.recommendation}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
