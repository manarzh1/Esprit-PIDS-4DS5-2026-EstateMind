"use client";
import { useEffect, useRef, useState } from "react";
import { Database, ShieldCheck, Scale, Sparkles, Cpu } from "lucide-react";
import { streamPipelineLogs } from "@/lib/api";

interface LogLine { t: string; msg: string; }

const STEPS = [
  { id:"collector", label:"Collector Agent",  desc:"Load + clean CSV datasets",    Icon:Database    },
  { id:"risk",      label:"Risk Detection",    desc:"Batch trust scoring",          Icon:ShieldCheck  },
  { id:"legal",     label:"Legal Agent",       desc:"RAG legal analysis",           Icon:Scale        },
  { id:"synth",     label:"Synthesizer",       desc:"Final report generation",      Icon:Sparkles     },
];

const logColor = (msg: string) =>
  msg.includes("✅") || msg.includes("💾") || msg.includes("📚") ? "var(--ok)"
  : msg.includes("❌") ? "var(--bad)" : "var(--txt)";

const detectStep = (msg: string) => {
  if (msg.includes("[Collector]") && (msg.includes("TERMINÉ")||msg.includes("DONE")||msg.includes("complete"))) return "collector";
  if (msg.includes("[Risk]")      && (msg.includes("TERMINÉ")||msg.includes("DONE")||msg.includes("complete"))) return "risk";
  if (msg.includes("[Legal]")     && (msg.includes("TERMINÉ")||msg.includes("DONE")||msg.includes("complete"))) return "legal";
  if (msg.includes("[Synthesizer]"))  return "synth";
  return null;
};

export default function BO6Page() {
  const [running,   setRunning]   = useState(false);
  const [logs,      setLogs]      = useState<LogLine[]>([]);
  const [done,      setDone]      = useState(false);
  const [stepsDone, setStepsDone] = useState<string[]>([]);
  const logRef  = useRef<HTMLDivElement>(null);
  const stopRef = useRef<(()=>void)|null>(null);

  useEffect(()=>{ if(logRef.current) logRef.current.scrollTop=logRef.current.scrollHeight; },[logs]);

  const run = () => {
    setRunning(true); setLogs([]); setDone(false); setStepsDone([]);
    const stop = streamPipelineLogs(
      (line) => {
        const t = new Date().toLocaleTimeString("en-US",{hour:"2-digit",minute:"2-digit",second:"2-digit"});
        setLogs(prev=>[...prev,{t,msg:line}]);
        const step=detectStep(line);
        if(step) setStepsDone(prev=>[...new Set([...prev,step])]);
      },
      ()=>{ setRunning(false); setDone(true); },
    );
    stopRef.current=stop;
  };

  useEffect(()=>()=>{ stopRef.current?.(); },[]);

  return (
    <div style={{display:"flex",flexDirection:"column",gap:20}}>
      {/* Header */}
      <div style={{display:"flex",alignItems:"center",gap:10}}>
        <span style={{display:"inline-block",background:"var(--mint)",color:"var(--green)",borderRadius:999,padding:"6px 14px",fontSize:11,fontWeight:800,textTransform:"uppercase",letterSpacing:".07em"}}>BO6</span>
        <span style={{fontSize:13,color:"var(--mut)",fontWeight:600}}>Platform Operations — LangGraph Pipeline · NLP · Orchestration</span>
      </div>

      <div>
        <h1 style={{fontFamily:"var(--font-display)",fontSize:26,fontWeight:600,marginBottom:4}}>Data Pipeline</h1>
        <p style={{fontSize:13,color:"var(--mut)"}}>LangGraph orchestration — collection, cleaning, trust scoring, legal analysis</p>
      </div>

      {/* Steps */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:14}}>
        {STEPS.map(({id,label,desc,Icon})=>{
          const isDone=done||stepsDone.includes(id);
          const isActive=running&&!isDone;
          return (
            <div key={id} className="panel" style={{
              padding:18,transition:"all .4s",
              borderColor:isDone?"rgba(47,156,126,.4)":isActive?"rgba(191,118,24,.3)":"rgba(255,255,255,.95)",
              background:isDone?"rgba(47,156,126,.04)":isActive?"rgba(191,118,24,.03)":"rgba(255,255,255,.82)",
            }}>
              <div style={{width:40,height:40,borderRadius:10,marginBottom:12,display:"flex",alignItems:"center",justifyContent:"center",
                background:isDone?"rgba(47,156,126,.15)":isActive?"rgba(191,118,24,.12)":"rgba(7,29,51,.05)"}}>
                <Icon size={18} color={isDone?"var(--ok)":isActive?"var(--warn)":"var(--mut)"}
                  style={{animation:isActive?"spin 2s linear infinite":"none"}}/>
              </div>
              <div style={{fontSize:13,fontWeight:700,marginBottom:3}}>{label}</div>
              <div style={{fontSize:11,color:"var(--mut)"}}>{desc}</div>
              {isDone&&<div style={{fontSize:11,color:"var(--ok)",marginTop:8,fontWeight:700}}>✓ Done</div>}
              {isActive&&<div style={{fontSize:11,color:"var(--warn)",marginTop:8,fontWeight:700}}>⟳ Running...</div>}
            </div>
          );
        })}
      </div>

      {/* Controls + log */}
      <div style={{display:"flex",gap:16,alignItems:"flex-start"}}>
        <div style={{display:"flex",flexDirection:"column",gap:8,flexShrink:0}}>
          <button className="btn-primary btn" onClick={run} disabled={running} style={{padding:"12px 20px",whiteSpace:"nowrap"}}>
            {running
              ? <><div style={{width:13,height:13,border:"2px solid rgba(255,255,255,.3)",borderTop:"2px solid white",borderRadius:"50%",animation:"spin 1s linear infinite"}}/> Running...</>
              : <><Cpu size={14}/> Launch Pipeline</>
            }
          </button>
          {running&&(
            <button className="btn" onClick={()=>{stopRef.current?.();setRunning(false);}} style={{padding:"10px 20px",color:"var(--bad)",borderColor:"rgba(204,59,37,.3)"}}>
              ■ Stop
            </button>
          )}
        </div>

        <div ref={logRef} style={{
          flex:1,background:"rgba(7,29,51,.03)",border:"1px solid var(--line)",borderRadius:14,
          padding:18,fontFamily:"var(--font-mono)",fontSize:12,
          minHeight:260,maxHeight:380,overflowY:"auto",backdropFilter:"blur(8px)",
        }}>
          {logs.length===0&&(
            <span style={{color:"var(--mut)"}}>$ Waiting for pipeline launch...</span>
          )}
          {logs.map((l,i)=>(
            <div key={i} style={{display:"flex",gap:12,marginBottom:4}}>
              <span style={{color:"var(--mut)",flexShrink:0,fontSize:10}}>{l.t}</span>
              <span style={{color:logColor(l.msg),lineHeight:1.5}}>{l.msg}</span>
            </div>
          ))}
          {done&&(
            <div style={{color:"var(--ok)",marginTop:10,borderTop:"1px solid var(--line)",paddingTop:10,fontSize:12,fontWeight:700}}>
              ✓ Pipeline completed successfully — listings_clean.csv ready
            </div>
          )}
        </div>
      </div>

      {/* Summary report */}
      {done&&(
        <div className="panel" style={{padding:24,borderColor:"rgba(47,156,126,.35)",background:"rgba(47,156,126,.04)"}}>
          <div style={{fontSize:14,fontWeight:700,color:"var(--navy)",marginBottom:16}}>Pipeline Report</div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:16}}>
            {[
              {label:"Cleaned listings",val:"8,412"},
              {label:"Avg trust score",  val:"0.673"},
              {label:"Suspects detected",val:"1,303"},
              {label:"High legal risk",  val:"412"},
            ].map(s=>(
              <div key={s.label} style={{textAlign:"center",background:"rgba(255,255,255,.8)",borderRadius:12,padding:"16px 12px"}}>
                <div style={{fontFamily:"var(--font-display)",fontSize:24,fontWeight:700,color:"var(--green)"}}>{s.val}</div>
                <div style={{fontSize:11,color:"var(--mut)",marginTop:4,fontWeight:600}}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Platform info */}
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
        <div className="panel" style={{padding:20}}>
          <div style={{fontSize:14,fontWeight:700,color:"var(--navy)",marginBottom:14}}>Pipeline Architecture</div>
          {[
            {step:"1",label:"Data Collector",tech:"BeautifulSoup · requests · CSV",icon:"📥"},
            {step:"2",label:"NLP Cleaner",tech:"spaCy · regex · fuzzy dedup",icon:"🧹"},
            {step:"3",label:"Trust Scorer",tech:"Random Forest · feature eng.",icon:"🛡"},
            {step:"4",label:"Legal Analyser",tech:"RAG · LangChain · Tunisian law",icon:"⚖"},
            {step:"5",label:"Synthesizer",tech:"LLM · JSON report generation",icon:"✨"},
          ].map(s=>(
            <div key={s.step} style={{display:"flex",alignItems:"center",gap:10,padding:"8px 0",borderBottom:"1px solid var(--line)"}}>
              <span style={{width:22,height:22,borderRadius:"50%",background:"var(--mint)",color:"var(--green)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:11,fontWeight:800,flexShrink:0}}>{s.step}</span>
              <span style={{fontSize:14}}>{s.icon}</span>
              <div style={{flex:1}}>
                <div style={{fontSize:13,fontWeight:600}}>{s.label}</div>
                <div style={{fontSize:10,color:"var(--mut)"}}>{s.tech}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="panel" style={{padding:20}}>
          <div style={{fontSize:14,fontWeight:700,color:"var(--navy)",marginBottom:14}}>System Status</div>
          {[
            {label:"Pipeline schedule",val:"Every 6 hours",ok:true},
            {label:"Data sources",val:"4 connected",ok:true},
            {label:"Last successful run",val:"Today 06:12",ok:true},
            {label:"Dataset quality",val:"82 / 100",ok:true},
            {label:"Listings processed",val:"14,927 raw",ok:true},
            {label:"API backend",val:"FastAPI running",ok:true},
          ].map(item=>(
            <div key={item.label} style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"9px 0",borderBottom:"1px solid var(--line)"}}>
              <span style={{fontSize:13,color:"var(--mut)"}}>{item.label}</span>
              <div style={{display:"flex",alignItems:"center",gap:6}}>
                <div style={{width:6,height:6,borderRadius:"50%",background:item.ok?"var(--ok)":"var(--bad)",flexShrink:0}}/>
                <span style={{fontSize:13,fontWeight:600}}>{item.val}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
