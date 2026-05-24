"use client";
/**
 * Estate Mind — NewDataToast.tsx
 * ================================
 * Popup impressionnant qui apparaît quand de nouvelles données
 * arrivent depuis le scraper (SSE depuis /api/notifications/stream).
 *
 * Usage dans layout.tsx :
 *   import { NewDataToast } from "@/components/NewDataToast";
 *   <NewDataToast />
 */

import { useEffect, useState, useRef, useCallback } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────
interface NotificationData {
  n_new:      number;
  n_fiable:   number;
  sources:    Record<string, number>;
  duration_s: number;
  run_id:     string;
}

interface Notification {
  type:      string;
  message:   string;
  data:      NotificationData;
  timestamp: string;
}

// ── Particules animées ────────────────────────────────────────────────────────
function Particle({ x, y, delay }: { x: number; y: number; delay: number }) {
  return (
    <div style={{
      position: "absolute",
      left: `${x}%`, top: `${y}%`,
      width: 6, height: 6,
      borderRadius: "50%",
      background: "var(--gold, #C8A96E)",
      opacity: 0,
      animation: `particleFly 1.2s ease-out ${delay}ms forwards`,
    }} />
  );
}

// ── Compteur animé ────────────────────────────────────────────────────────────
function AnimatedCounter({ target, duration = 1200 }: { target: number; duration?: number }) {
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    const steps  = 40;
    const step   = target / steps;
    const delay  = duration / steps;
    let   count  = 0;
    const timer  = setInterval(() => {
      count++;
      setCurrent(Math.min(Math.round(step * count), target));
      if (count >= steps) clearInterval(timer);
    }, delay);
    return () => clearInterval(timer);
  }, [target, duration]);

  return <>{current.toLocaleString("fr-FR")}</>;
}

// ── Composant principal ───────────────────────────────────────────────────────
export function NewDataToast() {
  const [notif,   setNotif]   = useState<Notification | null>(null);
  const [visible, setVisible] = useState(false);
  const [closing, setClosing] = useState(false);
  const esRef   = useRef<EventSource | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fermer le toast
  const close = useCallback(() => {
    setClosing(true);
    setTimeout(() => { setVisible(false); setClosing(false); setNotif(null); }, 400);
  }, []);

  // Connexion SSE
  useEffect(() => {
    const connect = () => {
      const es = new EventSource("/api/notifications/stream");
      esRef.current = es;

      es.onmessage = (e) => {
        try {
          const parsed: Notification = JSON.parse(e.data);
          if (parsed.type !== "new_data" || !parsed.data?.n_new) return;

          // Nouveau toast
          if (timerRef.current) clearTimeout(timerRef.current);
          setNotif(parsed);
          setVisible(true);
          setClosing(false);

          // Auto-fermeture après 8 secondes
          timerRef.current = setTimeout(() => close(), 8000);
        } catch {
          // heartbeat — ignorer
        }
      };

      es.onerror = () => {
        es.close();
        // Reconnecter après 5 secondes
        setTimeout(connect, 5000);
      };
    };

    connect();
    return () => {
      esRef.current?.close();
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [close]);

  if (!visible || !notif) return null;

  const { n_new, n_fiable, sources, duration_s } = notif.data;
  const sourceEntries = Object.entries(sources || {});
  const suspectCount  = n_new - (n_fiable || 0);
  const particles     = Array.from({ length: 12 }, (_, i) => ({
    x: Math.random() * 100, y: Math.random() * 100, delay: i * 80,
  }));

  return (
    <>
      {/* Styles keyframes */}
      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(110%); opacity: 0; }
          to   { transform: translateX(0);   opacity: 1; }
        }
        @keyframes slideOutRight {
          from { transform: translateX(0);   opacity: 1; }
          to   { transform: translateX(110%); opacity: 0; }
        }
        @keyframes particleFly {
          0%   { transform: scale(0) translateY(0);   opacity: 1; }
          60%  { transform: scale(1.5) translateY(-40px); opacity: 0.7; }
          100% { transform: scale(0) translateY(-80px); opacity: 0; }
        }
        @keyframes pulseGold {
          0%, 100% { box-shadow: 0 0 0 0 rgba(200,169,110,0.5); }
          50%      { box-shadow: 0 0 0 12px rgba(200,169,110,0); }
        }
        @keyframes shimmer {
          0%   { background-position: -200% center; }
          100% { background-position:  200% center; }
        }
        @keyframes countUp {
          from { transform: translateY(20px); opacity: 0; }
          to   { transform: translateY(0);    opacity: 1; }
        }
        @keyframes toastPulse {
          0%,100% { border-color: rgba(200,169,110,0.4); }
          50%     { border-color: rgba(200,169,110,0.9); }
        }
        @keyframes progressBar {
          from { width: 100%; }
          to   { width: 0%; }
        }
      `}</style>

      {/* Overlay sombre léger */}
      <div
        onClick={close}
        style={{
          position: "fixed", inset: 0, zIndex: 9998,
          background: "rgba(0,0,0,0.15)",
          animation: closing ? "none" : "none",
        }}
      />

      {/* Toast principal */}
      <div style={{
        position: "fixed",
        bottom: 24, right: 24,
        width: 380,
        zIndex: 9999,
        animation: closing
          ? "slideOutRight 0.4s cubic-bezier(.36,.07,.19,.97) forwards"
          : "slideInRight 0.5s cubic-bezier(.34,1.56,.64,1) forwards",
        fontFamily: "'DM Sans', 'Segoe UI', system-ui, sans-serif",
      }}>
        <div style={{
          background: "linear-gradient(135deg, #09090B 0%, #131316 100%)",
          border: "1px solid rgba(200,169,110,0.5)",
          borderRadius: 16,
          overflow: "hidden",
          boxShadow: "0 24px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(200,169,110,0.1)",
          animation: "toastPulse 2s ease-in-out infinite",
          position: "relative",
        }}>

          {/* Particules */}
          <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
            {particles.map((p, i) => (
              <Particle key={i} x={p.x} y={p.y} delay={p.delay} />
            ))}
          </div>

          {/* Header shimmer */}
          <div style={{
            padding: "14px 16px 10px",
            background: "linear-gradient(90deg, transparent 0%, rgba(200,169,110,0.08) 50%, transparent 100%)",
            backgroundSize: "200% auto",
            animation: "shimmer 2s linear infinite",
            borderBottom: "1px solid rgba(200,169,110,0.15)",
            display: "flex", alignItems: "center", gap: 10,
          }}>
            {/* Icône pulsante */}
            <div style={{
              width: 42, height: 42, borderRadius: 10, flexShrink: 0,
              background: "rgba(200,169,110,0.12)",
              border: "1px solid rgba(200,169,110,0.3)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 20,
              animation: "pulseGold 1.5s ease-in-out infinite",
            }}>
              🏠
            </div>

            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, color: "rgba(200,169,110,0.7)", fontWeight: 600,
                textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 2 }}>
                Nouvelles données
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "white" }}>
                Marché mis à jour ! 🚀
              </div>
            </div>

            {/* Bouton fermer */}
            <button
              onClick={(e) => { e.stopPropagation(); close(); }}
              style={{
                background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 6, width: 24, height: 24, cursor: "pointer",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 12, color: "rgba(255,255,255,0.5)", flexShrink: 0,
              }}
            >
              ✕
            </button>
          </div>

          {/* Body */}
          <div style={{ padding: "14px 16px" }}>

            {/* Compteur principal */}
            <div style={{
              display: "flex", alignItems: "center", gap: 12, marginBottom: 14,
              animation: "countUp 0.6s ease-out 200ms both",
            }}>
              <div style={{
                fontSize: 48, fontWeight: 800, lineHeight: 1,
                background: "linear-gradient(135deg, #C8A96E 0%, #F0D080 50%, #C8A96E 100%)",
                WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}>
                +<AnimatedCounter target={n_new} />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "white" }}>
                  annonces ajoutées
                </div>
                <div style={{ fontSize: 11, color: "rgba(255,255,255,0.5)", marginTop: 2 }}>
                  en {duration_s}s · {new Date(notif.timestamp).toLocaleTimeString("fr-FR")}
                </div>
              </div>
            </div>

            {/* Stats inline */}
            <div style={{
              display: "grid", gridTemplateColumns: "1fr 1fr",
              gap: 8, marginBottom: 12,
            }}>
              <div style={{
                padding: "8px 10px", borderRadius: 8,
                background: "rgba(22,163,74,0.1)", border: "1px solid rgba(22,163,74,0.25)",
                animation: "countUp 0.6s ease-out 400ms both",
              }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: "#22C55E" }}>
                  <AnimatedCounter target={n_fiable} />
                </div>
                <div style={{ fontSize: 10, color: "rgba(255,255,255,0.5)", marginTop: 2 }}>
                  Fiables ✓
                </div>
              </div>

              <div style={{
                padding: "8px 10px", borderRadius: 8,
                background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.25)",
                animation: "countUp 0.6s ease-out 500ms both",
              }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: "#EF4444" }}>
                  <AnimatedCounter target={suspectCount} />
                </div>
                <div style={{ fontSize: 10, color: "rgba(255,255,255,0.5)", marginTop: 2 }}>
                  Suspects ⚠
                </div>
              </div>
            </div>

            {/* Sources */}
            {sourceEntries.length > 0 && (
              <div style={{
                display: "flex", gap: 6, flexWrap: "wrap",
                animation: "countUp 0.6s ease-out 600ms both",
              }}>
                {sourceEntries.map(([src, count]) => (
                  <span key={src} style={{
                    padding: "3px 8px", borderRadius: 99, fontSize: 11,
                    background: "rgba(200,169,110,0.1)",
                    border: "1px solid rgba(200,169,110,0.25)",
                    color: "rgba(200,169,110,0.9)",
                    fontWeight: 500,
                  }}>
                    {src} +{count}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Barre de progression auto-fermeture */}
          <div style={{ height: 3, background: "rgba(255,255,255,0.05)" }}>
            <div style={{
              height: "100%",
              background: "linear-gradient(90deg, #C8A96E, #F0D080)",
              animation: "progressBar 8s linear forwards",
              transformOrigin: "left",
            }} />
          </div>
        </div>
      </div>
    </>
  );
}
