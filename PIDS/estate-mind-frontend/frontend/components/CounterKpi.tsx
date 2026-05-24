"use client";
/**
 * Estate Mind — CounterKpi
 * KPI animé qui compte jusqu'à sa valeur finale (easing out).
 * Remplace les KPIs statiques du Dashboard.
 */
import { useEffect, useRef, useState } from "react";
import { TrendingUp, TrendingDown } from "lucide-react";

interface Props {
  label:        string;
  value:        number | string;
  color?:       string;
  sub?:         string;
  prev?:        number;
  higherIsBetter?: boolean;
  prefix?:      string;   // ex: "+"
  suffix?:      string;   // ex: "%", " TND"
  decimals?:    number;
  icon?:        React.ReactNode;
  duration?:    number;   // ms d'animation (défaut 1200)
}

function easeOut(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

export function CounterKpi({
  label, value, color = "var(--gold)", sub, prev,
  higherIsBetter = true, prefix = "", suffix = "",
  decimals = 0, icon, duration = 1200,
}: Props) {
  const [displayed, setDisplayed] = useState(0);
  const frameRef  = useRef<number | null>(null);
  const startRef  = useRef<number | null>(null);
  const isNumber  = typeof value === "number";
  const target    = isNumber ? value : 0;

  useEffect(() => {
    if (!isNumber) return;
    startRef.current = null;

    const animate = (ts: number) => {
      if (!startRef.current) startRef.current = ts;
      const elapsed  = ts - startRef.current;
      const progress = Math.min(elapsed / duration, 1);
      const eased    = easeOut(progress);
      setDisplayed(eased * target);
      if (progress < 1) frameRef.current = requestAnimationFrame(animate);
    };

    frameRef.current = requestAnimationFrame(animate);
    return () => { if (frameRef.current) cancelAnimationFrame(frameRef.current); };
  }, [target, duration, isNumber]);

  // Delta vs valeur précédente
  const hasDelta = prev !== undefined && prev !== null && typeof value === "number";
  const delta    = hasDelta ? ((value as number) - prev!) / Math.abs(prev!) * 100 : 0;
  const deltaGood= higherIsBetter ? delta > 0 : delta < 0;
  const deltaC   = deltaGood ? "var(--ok)" : "var(--bad)";

  const formatted = isNumber
    ? (decimals > 0
        ? displayed.toFixed(decimals)
        : Math.round(displayed).toLocaleString("fr-FR"))
    : String(value);

  return (
    <div
      style={{
        background: "var(--card)", border: "1px solid var(--bor)",
        borderRadius: 12, padding: "18px 20px",
        transition: "border-color .2s, box-shadow .2s",
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.borderColor = "var(--gbor)";
        (e.currentTarget as HTMLElement).style.boxShadow = `0 0 0 1px rgba(200,169,110,.15)`;
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.borderColor = "var(--bor)";
        (e.currentTarget as HTMLElement).style.boxShadow = "none";
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ flex: 1 }}>
          <div style={{
            fontSize: 10, color: "var(--mut)", textTransform: "uppercase",
            letterSpacing: ".07em", marginBottom: 6,
          }}>{label}</div>

          <div style={{
            fontFamily: "var(--font-display)", fontSize: 28, fontWeight: 700,
            color, lineHeight: 1, letterSpacing: "-.01em",
          }}>
            {prefix}{formatted}{suffix}
          </div>

          {/* Delta animé */}
          {hasDelta && (
            <div style={{
              display: "flex", alignItems: "center", gap: 4,
              fontSize: 11, color: deltaC, marginTop: 5,
            }}>
              {delta > 0
                ? <TrendingUp size={10} />
                : <TrendingDown size={10} />}
              <span style={{ fontWeight: 500 }}>
                {delta > 0 ? "+" : ""}{delta.toFixed(1)}%
              </span>
              <span style={{ color: "var(--mut)", fontSize: 9 }}>vs précédent</span>
            </div>
          )}

          {sub && (
            <div style={{ fontSize: 10, color: "var(--mut)", marginTop: 4 }}>{sub}</div>
          )}
        </div>

        {icon && (
          <div style={{
            width: 36, height: 36, borderRadius: 9, flexShrink: 0,
            background: `${color}12`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}
