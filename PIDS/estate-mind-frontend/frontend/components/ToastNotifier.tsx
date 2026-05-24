"use client";
/**
 * Estate Mind — ToastNotifier
 * Système de notifications toast global.
 *
 * Usage :
 *   import { useToast } from "@/components/ToastNotifier";
 *   const toast = useToast();
 *   toast.success("Pipeline terminé !");
 *   toast.warn("Nouvelle alerte : Hammamet +15%");
 *   toast.error("Source Tayara indisponible");
 *   toast.info("47 nouvelles annonces collectées");
 */
"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { CheckCircle, AlertTriangle, XCircle, Info, X } from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────
type ToastType = "success" | "warn" | "error" | "info";
interface Toast { id: number; type: ToastType; message: string; duration: number; }

// ── Contexte ──────────────────────────────────────────────────────────────────
const ToastCtx = createContext<{
  success:(msg:string,d?:number)=>void;
  warn:   (msg:string,d?:number)=>void;
  error:  (msg:string,d?:number)=>void;
  info:   (msg:string,d?:number)=>void;
}>({ success:()=>{}, warn:()=>{}, error:()=>{}, info:()=>{} });

// ── Hook ──────────────────────────────────────────────────────────────────────
export const useToast = () => useContext(ToastCtx);

// ── Config visuelle par type ──────────────────────────────────────────────────
const TOAST_CFG: Record<ToastType, {
  bg:string; border:string; color:string; Icon:React.FC<any>;
}> = {
  success:{ bg:"rgba(29,158,117,.12)", border:"rgba(29,158,117,.3)",  color:"#1D9E75", Icon:CheckCircle  },
  warn:   { bg:"rgba(232,168,76,.12)", border:"rgba(232,168,76,.3)",  color:"#E8A84C", Icon:AlertTriangle},
  error:  { bg:"rgba(224,92,92,.12)", border:"rgba(224,92,92,.3)",   color:"#E05C5C", Icon:XCircle      },
  info:   { bg:"rgba(107,159,232,.12)",border:"rgba(107,159,232,.3)",color:"#6B9FE8", Icon:Info         },
};

// ── Composant toast individuel ────────────────────────────────────────────────
function ToastItem({ toast, onRemove }: { toast: Toast; onRemove:(id:number)=>void }) {
  const [visible, setVisible] = useState(false);
  const cfg = TOAST_CFG[toast.type];

  useEffect(() => {
    // Entrée
    const t1 = setTimeout(() => setVisible(true), 20);
    // Sortie
    const t2 = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onRemove(toast.id), 300);
    }, toast.duration);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  return (
    <div style={{
      display: "flex", alignItems: "flex-start", gap: 10,
      background: cfg.bg, border: `1px solid ${cfg.border}`,
      borderRadius: 10, padding: "12px 14px",
      boxShadow: "0 8px 24px rgba(0,0,0,.4)",
      minWidth: 260, maxWidth: 360,
      transform: visible ? "translateX(0) scale(1)" : "translateX(100%) scale(0.95)",
      opacity: visible ? 1 : 0,
      transition: "all .28s cubic-bezier(.4,0,.2,1)",
    }}>
      <cfg.Icon size={15} color={cfg.color} style={{ flexShrink: 0, marginTop: 1 }} />
      <span style={{ fontSize: 12, color: "var(--txt)", lineHeight: 1.5, flex: 1 }}>
        {toast.message}
      </span>
      <button onClick={() => { setVisible(false); setTimeout(() => onRemove(toast.id), 300); }}
        style={{ background:"none",border:"none",cursor:"pointer",color:"var(--mut)",padding:0,flexShrink:0 }}>
        <X size={12} />
      </button>
    </div>
  );
}

// ── Provider + conteneur ──────────────────────────────────────────────────────
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counter = useRef(0);

  const add = useCallback((type: ToastType, message: string, duration = 4000) => {
    const id = ++counter.current;
    setToasts(prev => [...prev.slice(-4), { id, type, message, duration }]); // max 5
  }, []);

  const remove = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const ctx = {
    success: (m:string,d?:number) => add("success",m,d),
    warn:    (m:string,d?:number) => add("warn",m,d),
    error:   (m:string,d?:number) => add("error",m,d),
    info:    (m:string,d?:number) => add("info",m,d),
  };

  return (
    <ToastCtx.Provider value={ctx}>
      {children}
      {/* Conteneur en bas à droite */}
      <div style={{
        position: "fixed", bottom: 20, right: 20,
        display: "flex", flexDirection: "column", gap: 8,
        zIndex: 9999, pointerEvents: "none",
      }}>
        {toasts.map(t => (
          <div key={t.id} style={{ pointerEvents: "all" }}>
            <ToastItem toast={t} onRemove={remove} />
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
