"use client";

interface GaugeProps {
  value:     number;   // 0 à 1
  size?:     number;   // diamètre en px (défaut 80)
  label?:    string;
  color?:    string;   // couleur de l'arc (auto si absent)
  showValue?: boolean;
}

export function Gauge({ value, size = 80, label, color, showValue = true }: GaugeProps) {
  const clampedValue = Math.max(0, Math.min(1, value));

  // Arc SVG : demi-cercle (180°)
  const r      = (size / 2) * 0.8;
  const cx     = size / 2;
  const cy     = size / 2;
  const stroke = size * 0.12;

  // Couleur automatique selon la valeur
  const arcColor = color || (
    clampedValue >= 0.75 ? "#52C896" :
    clampedValue >= 0.50 ? "#E8A84C" :
    "#E05C5C"
  );

  // Calcul de l'arc (partie colorée)
  const startAngle = -180;  // gauche
  const endAngle   = 0;     // droite
  const totalAngle = endAngle - startAngle;
  const fillAngle  = startAngle + totalAngle * clampedValue;

  function polarToCartesian(cx: number, cy: number, r: number, deg: number) {
    const rad = (deg * Math.PI) / 180;
    return {
      x: cx + r * Math.cos(rad),
      y: cy + r * Math.sin(rad),
    };
  }

  const start  = polarToCartesian(cx, cy, r, startAngle);
  const end    = polarToCartesian(cx, cy, r, endAngle);
  const filled = polarToCartesian(cx, cy, r, fillAngle);

  const bgPath = [
    `M ${start.x} ${start.y}`,
    `A ${r} ${r} 0 0 1 ${end.x} ${end.y}`,
  ].join(" ");

  const largeArc = fillAngle - startAngle > 180 ? 1 : 0;
  const fgPath = clampedValue > 0 ? [
    `M ${start.x} ${start.y}`,
    `A ${r} ${r} 0 ${largeArc} 1 ${filled.x} ${filled.y}`,
  ].join(" ") : "";

  const pct = Math.round(clampedValue * 100);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <div style={{ position: "relative", width: size, height: size / 2 + stroke }}>
        <svg width={size} height={size / 2 + stroke} viewBox={`0 0 ${size} ${size / 2 + stroke}`}>
          {/* Arc de fond */}
          <path
            d={bgPath}
            fill="none"
            stroke="var(--bor)"
            strokeWidth={stroke}
            strokeLinecap="round"
          />
          {/* Arc coloré */}
          {fgPath && (
            <path
              d={fgPath}
              fill="none"
              stroke={arcColor}
              strokeWidth={stroke}
              strokeLinecap="round"
            />
          )}
        </svg>

        {showValue && (
          <div style={{
            position: "absolute",
            bottom: 0,
            left: "50%",
            transform: "translateX(-50%)",
            fontFamily: "var(--font-display)",
            fontSize: size * 0.2,
            fontWeight: 700,
            color: arcColor,
            whiteSpace: "nowrap",
          }}>
            {pct}%
          </div>
        )}
      </div>

      {label && (
        <div style={{ fontSize: 11, color: "var(--mut)", textAlign: "center" }}>
          {label}
        </div>
      )}
    </div>
  );
}
