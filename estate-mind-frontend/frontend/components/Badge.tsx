"use client";

interface BadgeProps {
  level: "Faible" | "Moyen" | "Élevé" | string;
}

const COLORS: Record<string, { bg: string; color: string; border: string }> = {
  "Faible":  { bg: "#52C89614", color: "#52C896", border: "#52C89622" },
  "Moyen":   { bg: "#E8A84C14", color: "#E8A84C", border: "#E8A84C22" },
  "Élevé":   { bg: "#E05C5C14", color: "#E05C5C", border: "#E05C5C22" },
  "Fiable":  { bg: "#52C89614", color: "#52C896", border: "#52C89622" },
  "Suspect": { bg: "#E05C5C14", color: "#E05C5C", border: "#E05C5C22" },
};

export function Badge({ level }: BadgeProps) {
  const style = COLORS[level] ?? { bg: "#88888814", color: "#888888", border: "#88888822" };

  return (
    <span style={{
      display:      "inline-block",
      padding:      "2px 8px",
      borderRadius: 999,
      fontSize:     10,
      fontWeight:   500,
      background:   style.bg,
      color:        style.color,
      border:       `1px solid ${style.border}`,
      whiteSpace:   "nowrap",
    }}>
      {level}
    </span>
  );
}
