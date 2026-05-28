"use client";

interface KpiCardProps {
  label:    string;
  value:    string | number;
  sub?:     string;
  color?:   string;
  icon?:    React.ReactNode;
  delta?:   number;         // variation en % vs run précédent
  higherIsBetter?: boolean;
}

export function KpiCard({
  label, value, sub, color = "var(--txt)", icon, delta, higherIsBetter = true,
}: KpiCardProps) {
  const showDelta = delta !== undefined && delta !== null && !isNaN(delta);
  const positive  = delta !== undefined && delta > 0;
  const good      = higherIsBetter ? positive : !positive;
  const deltaColor = good ? "var(--ok)" : "var(--bad)";

  return (
    <div className="card" style={{ padding: "18px 20px" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div style={{ flex: 1 }}>
          <div style={{
            fontSize: 10, color: "var(--mut)",
            textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 6,
          }}>
            {label}
          </div>

          <div style={{
            fontFamily: "var(--font-display)", fontSize: 26,
            fontWeight: 600, color,
          }}>
            {typeof value === "number" ? value.toLocaleString("fr-FR") : value}
          </div>

          {showDelta && (
            <div style={{ display: "flex", alignItems: "center", gap: 3, fontSize: 10, color: deltaColor, marginTop: 3 }}>
              <span>{positive ? "+" : ""}{delta!.toFixed(1)}%</span>
              <span style={{ color: "var(--mut)", fontSize: 9 }}>vs run précédent</span>
            </div>
          )}

          {sub && (
            <div style={{ fontSize: 10, color: "var(--mut)", marginTop: 3 }}>{sub}</div>
          )}
        </div>

        {icon && (
          <div style={{ color: "var(--mut)", flexShrink: 0 }}>{icon}</div>
        )}
      </div>
    </div>
  );
}
