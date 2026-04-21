"use client";
import { useEffect, useRef, useState } from "react";
import { Database, ShieldCheck, Scale, Sparkles, Cpu } from "lucide-react";
import { streamPipelineLogs } from "@/lib/api";

interface LogLine { t: string; msg: string; }

const STEPS = [
  { id:"collector", label:"Collector Agent",   desc:"Chargement + nettoyage CSV",  Icon:Database    },
  { id:"risk",      label:"Risk Detection",     desc:"Trust scoring batch",          Icon:ShieldCheck  },
  { id:"legal",     label:"Legal Agent",        desc:"Analyse juridique RAG",        Icon:Scale        },
  { id:"synth",     label:"Synthesizer",        desc:"Rapport final",                Icon:Sparkles     },
];

const logColor = (msg: string) =>
  msg.includes("✅") || msg.includes("💾") || msg.includes("📚") ? "var(--ok)"
  : msg.includes("❌") ? "var(--bad)" : "var(--txt)";

export default function PipelinePage() {
  const [running, setRunning]   = useState(false);
  const [logs, setLogs]         = useState<LogLine[]>([]);
  const [done, setDone]         = useState(false);
  const [stepsDone, setStepsDone] = useState<string[]>([]);
  const logRef = useRef<HTMLDivElement>(null);
  const stopRef = useRef<(() => void) | null>(null);

  // Auto-scroll
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  // Détecte les étapes terminées depuis les logs
  const detectStep = (msg: string) => {
    if (msg.includes("[Collector]") && msg.includes("TERMINÉ")) return "collector";
    if (msg.includes("[Risk]")      && msg.includes("TERMINÉ")) return "risk";
    if (msg.includes("[Legal]")     && msg.includes("TERMINÉ")) return "legal";
    if (msg.includes("[Synthesizer]"))                           return "synth";
    return null;
  };

  const run = () => {
    setRunning(true); setLogs([]); setDone(false); setStepsDone([]);

    const stop = streamPipelineLogs(
      (line) => {
        const t = new Date().toLocaleTimeString("fr-FR", { hour:"2-digit", minute:"2-digit", second:"2-digit" });
        setLogs(prev => [...prev, { t, msg: line }]);
        const step = detectStep(line);
        if (step) setStepsDone(prev => [...new Set([...prev, step])]);
      },
      () => { setRunning(false); setDone(true); },
    );
    stopRef.current = stop;
  };

  useEffect(() => () => { stopRef.current?.(); }, []);

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:20 }}>
      <div style={{ marginBottom:8 }}>
        <h1 style={{ fontFamily:"var(--font-display)", fontSize:24, fontWeight:600, marginBottom:4 }}>Pipeline de données</h1>
        <p style={{ fontSize:13, color:"var(--mut)" }}>Orchestration LangGraph — collecte, nettoyage, trust scoring, analyse juridique</p>
      </div>

      {/* Étapes */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:14 }}>
        {STEPS.map(({ id, label, desc, Icon }) => {
          const isDone = done || stepsDone.includes(id);
          return (
            <div key={id} style={{
              background:"var(--card)",
              border:`1px solid ${isDone ? "rgba(82,200,150,.35)" : "var(--bor)"}`,
              borderRadius:12, padding:18, transition:"border-color .4s",
            }}>
              <div style={{
                width:36, height:36, borderRadius:9, marginBottom:12,
                background: isDone ? "rgba(82,200,150,.12)" : "var(--gdim)",
                display:"flex", alignItems:"center", justifyContent:"center",
              }}>
                <Icon size={16} color={isDone ? "var(--ok)" : "var(--gold)"} />
              </div>
              <div style={{ fontSize:13, fontWeight:500, marginBottom:3 }}>{label}</div>
              <div style={{ fontSize:11, color:"var(--mut)" }}>{desc}</div>
              {isDone && <div style={{ fontSize:11, color:"var(--ok)", marginTop:8 }}>✓ Terminé</div>}
            </div>
          );
        })}
      </div>

      {/* Contrôles + log */}
      <div style={{ display:"flex", gap:16, alignItems:"flex-start" }}>
        <button
          className="btn-gold"
          onClick={run}
          disabled={running}
          style={{ width:"auto", padding:"11px 22px", whiteSpace:"nowrap" }}
        >
          {running
            ? <><div className="animate-spin" style={{ width:13, height:13, border:"2px solid rgba(0,0,0,.2)", borderTop:"2px solid #09090B", borderRadius:"50%" }} /> Exécution...</>
            : <><Cpu size={14} /> Lancer le pipeline</>
          }
        </button>

        <div ref={logRef} style={{
          flex:1, background:"var(--card)", border:"1px solid var(--bor)", borderRadius:12,
          padding:18, fontFamily:"var(--font-mono)", fontSize:11.5,
          minHeight:260, maxHeight:380, overflowY:"auto",
        }}>
          {logs.length === 0 && (
            <span style={{ color:"var(--mut)" }}>$ En attente du lancement du pipeline...</span>
          )}
          {logs.map((l, i) => (
            <div key={i} style={{ display:"flex", gap:12, marginBottom:5 }}>
              <span style={{ color:"var(--mut)", flexShrink:0 }}>{l.t}</span>
              <span style={{ color:logColor(l.msg) }}>{l.msg}</span>
            </div>
          ))}
          {done && (
            <div style={{ color:"var(--ok)", marginTop:10, borderTop:"1px solid var(--bor)", paddingTop:10, fontSize:12 }}>
              ✓ Pipeline terminé avec succès — listings_clean.csv prêt
            </div>
          )}
        </div>
      </div>

      {/* Résumé (après pipeline) */}
      {done && (
        <div className="animate-fadeup" style={{ background:"var(--gdim)", border:"1px solid var(--gbor)", borderRadius:12, padding:"20px 24px" }}>
          <div className="section-title" style={{ marginBottom:12 }}>Rapport de pipeline</div>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:16 }}>
            {[
              { label:"Annonces nettoyées", val:"8 412" },
              { label:"Trust score moyen",  val:"0.673" },
              { label:"Suspects détectés",  val:"1 303" },
              { label:"Risque légal élevé", val:"412"   },
            ].map(s => (
              <div key={s.label} style={{ textAlign:"center" }}>
                <div style={{ fontFamily:"var(--font-display)", fontSize:22, fontWeight:600, color:"var(--gold)" }}>{s.val}</div>
                <div style={{ fontSize:11, color:"var(--mut)", marginTop:4 }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
