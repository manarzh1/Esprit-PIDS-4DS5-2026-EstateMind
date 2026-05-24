"use client";
/**
 * Estate Mind — SentimentBadge + TrustBreakdown (BO2)
 * Affiche le résultat du sentiment LLM + décomposition du trust score enrichi.
 * Utilisé dans : app/analyse/page.tsx, app/recherche/page.tsx
 */
import { useState, useCallback } from "react";
import { Shield, AlertTriangle, CheckCircle, Minus, ChevronDown, ChevronUp } from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────────
interface SentimentData {
  sentiment_score:    number;
  sentiment_label:    string;
  manipulation_flags: string[];
  confidence:         number;
  details:            string;
  method:             string;
}

interface TrustBreakdown {
  sentiment_llm:      { score: number; weight: string };
  data_coherence:     { score: number; weight: string };
  fraud_detection:    { score: number; weight: string };
  completeness:       { score: number; weight: string };
  source_reliability: { score: number; weight: string };
}

interface TrustEnrichedData {
  trust_enriched:       number;
  trust_level_enriched: string;
  trust_breakdown:      TrustBreakdown;
  sentiment:            SentimentData;
  trust_gru?:           any;
}

// ── Helpers ────────────────────────────────────────────────────────────────────
const LABEL_META: Record<string, { color: string; icon: string; text: string }> = {
  positif_fiable:  { color: "#1D9E75", icon: "✅", text: "Positif & Fiable" },
  neutre:          { color: "var(--mut)", icon: "⬜", text: "Neutre" },
  positif_suspect: { color: "#E8A84C", icon: "⚠️", text: "Positif mais Suspect" },
  negatif:         { color: "#E05C5C", icon: "❌", text: "Négatif" },
  spam:            { color: "#E05C5C", icon: "🚫", text: "Spam / Fraude" },
};

const FLAG_LABELS: Record<string, string> = {
  urgence_artificielle:    "Urgence artificielle",
  superlatifs_vagues:      "Superlatifs sans données",
  juridique_suspect:       "Termes juridiques suspects",
  spam_indicators:         "Indicateurs spam",
  description_vide_ou_trop_courte: "Description trop courte",
  no_description:          "Aucune description",
};

// ── Composant Sentiment seul ───────────────────────────────────────────────────
export function SentimentBadge({ data }: { data: SentimentData }) {
  const meta = LABEL_META[data.sentiment_label] || LABEL_META["neutre"];
  const pct  = Math.round(data.sentiment_score * 100);

  return (
    <div style={{
      background: `${meta.color}08`, border: `1px solid ${meta.color}25`,
      borderRadius: 8, padding: "10px 12px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span style={{ fontSize: 14 }}>{meta.icon}</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: meta.color }}>
          Sentiment : {meta.text}
        </span>
        <span style={{
          marginLeft: "auto", fontSize: 14, fontWeight: 700,
          fontFamily: "var(--font-display)", color: meta.color,
        }}>{pct}%</span>
      </div>

      {/* Barre de progression */}
      <div style={{ height: 4, background: "var(--el)", borderRadius: 2, overflow: "hidden", marginBottom: 8 }}>
        <div style={{ height: "100%", width: `${pct}%`, background: meta.color, borderRadius: 2 }} />
      </div>

      <p style={{ fontSize: 11, color: "var(--mut)", lineHeight: 1.5, margin: 0, marginBottom: data.manipulation_flags.length ? 8 : 0 }}>
        {data.details}
      </p>

      {/* Flags de manipulation */}
      {data.manipulation_flags.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {data.manipulation_flags.map(flag => (
            <span key={flag} style={{
              fontSize: 9, padding: "2px 7px", borderRadius: 999,
              background: "rgba(232,168,76,.12)", color: "#E8A84C",
              border: "1px solid rgba(232,168,76,.3)",
            }}>
              ⚠ {FLAG_LABELS[flag] || flag}
            </span>
          ))}
        </div>
      )}

      <div style={{ fontSize: 9, color: "var(--mut)", marginTop: 6 }}>
        Via {data.method === "llm+heuristic" ? "LLM + heuristiques" : data.method === "llm" ? "LLM" : "Heuristiques"} · Confiance {Math.round(data.confidence * 100)}%
      </div>
    </div>
  );
}

// ── Composant Trust Score Enrichi ──────────────────────────────────────────────
export function TrustBreakdownCard({ data }: { data: TrustEnrichedData }) {
  const [expanded, setExpanded] = useState(false);
  const tc = data.trust_enriched >= .75 ? "#1D9E75"
           : data.trust_enriched >= .50 ? "#E8A84C" : "#E05C5C";

  const signals = [
    { key: "sentiment_llm",      label: "Analyse sentiment LLM", icon: "🧠", ...data.trust_breakdown.sentiment_llm },
    { key: "data_coherence",     label: "Cohérence données",      icon: "📊", ...data.trust_breakdown.data_coherence },
    { key: "fraud_detection",    label: "Détection fraude",       icon: "🔍", ...data.trust_breakdown.fraud_detection },
    { key: "completeness",       label: "Complétude annonce",     icon: "📋", ...data.trust_breakdown.completeness },
    { key: "source_reliability", label: "Fiabilité source",       icon: "🏢", ...data.trust_breakdown.source_reliability },
  ];

  return (
    <div style={{
      background: `${tc}06`, border: `1px solid ${tc}22`,
      borderRadius: 10, overflow: "hidden",
    }}>
      {/* Header */}
      <div style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 12 }}
        onClick={() => setExpanded(e => !e)} className="cursor-pointer">
        <div>
          <div style={{ fontSize: 10, color: "var(--mut)", textTransform: "uppercase",
            letterSpacing: ".05em", marginBottom: 2 }}>Trust Score Enrichi</div>
          <div style={{ fontFamily: "var(--font-display)", fontSize: 26, fontWeight: 700, color: tc }}>
            {data.trust_enriched.toFixed(3)}
          </div>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ height: 6, background: "var(--el)", borderRadius: 3, overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${data.trust_enriched * 100}%`, background: tc, borderRadius: 3 }} />
          </div>
          <div style={{ fontSize: 11, color: tc, fontWeight: 500, marginTop: 4 }}>
            {data.trust_level_enriched}
          </div>
        </div>
        <div style={{ flexShrink: 0 }}>
          <button style={{ background: "none", border: "none", cursor: "pointer", color: "var(--mut)" }}>
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {/* Décomposition 5 signaux */}
      {expanded && (
        <div style={{ borderTop: "1px solid var(--bor)", padding: "12px 16px" }}>
          <div style={{ fontSize: 10, color: "var(--mut)", marginBottom: 10, fontWeight: 500 }}>
            DÉCOMPOSITION DES 5 SIGNAUX
          </div>
          {signals.map(sig => {
            const sigC = sig.score >= .75 ? "#1D9E75" : sig.score >= .50 ? "#E8A84C" : "#E05C5C";
            return (
              <div key={sig.key} style={{ marginBottom: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between",
                  alignItems: "center", marginBottom: 3 }}>
                  <span style={{ fontSize: 11, color: "var(--txt)" }}>
                    {sig.icon} {sig.label}
                  </span>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: 9, color: "var(--mut)" }}>{sig.weight}</span>
                    <span style={{ fontSize: 12, fontWeight: 600, color: sigC,
                      fontFamily: "var(--font-display)", minWidth: 36, textAlign: "right" }}>
                      {sig.score.toFixed(2)}
                    </span>
                  </div>
                </div>
                <div style={{ height: 3, background: "var(--el)", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${sig.score * 100}%`,
                    background: sigC, borderRadius: 2 }} />
                </div>
              </div>
            );
          })}

          {/* Note sur la méthode */}
          <div style={{ fontSize: 10, color: "var(--mut)", marginTop: 10, lineHeight: 1.5,
            padding: "6px 8px", background: "var(--el)", borderRadius: 6 }}>
            <b>Méthode :</b> Trust Score = 25% Sentiment LLM + 25% Cohérence données
            + 20% Anti-fraude + 15% Complétude + 15% Source
            {data.trust_gru && (
              <span> · GRU classe : <b style={{ color: tc }}>{data.trust_gru.predicted_class}</b>
                {" "}(P={data.trust_gru.probabilities?.[data.trust_gru.predicted_class]?.toFixed(2)})
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Widget combiné pour la page Analyser ──────────────────────────────────────
export function FullTrustAnalysis({
  description, price, surface, city, propertyType, source
}: {
  description: string; price: number; surface: number;
  city: string; propertyType: string; source: string;
}) {
  const [data,    setData]    = useState<TrustEnrichedData | null>(null);
  const [loading, setLoading] = useState(false);

  const analyze = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch("/api/analyze-enriched", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          description, price, surface, city,
          property_type: propertyType, source, use_llm: true,
        }),
      });
      if (r.ok) setData(await r.json());
    } catch {}
    setLoading(false);
  }, [description, price, surface, city, propertyType, source]);

  if (!data && !loading) {
    return (
      <button onClick={analyze} style={{
        width: "100%", padding: "10px 0", borderRadius: 8,
        border: "1px solid rgba(200,169,110,.3)", background: "rgba(200,169,110,.06)",
        color: "var(--gold)", cursor: "pointer", fontSize: 12, fontWeight: 500,
        fontFamily: "var(--font-body)",
      }}>
        🧠 Analyser avec IA (Sentiment + GRU + Trust enrichi)
      </button>
    );
  }

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: "16px 0" }}>
        <div style={{ width: 20, height: 20, border: "2px solid var(--gbor)",
          borderTop: "2px solid var(--gold)", borderRadius: "50%",
          animation: "spin 1s linear infinite" }} />
      </div>
    );
  }

  if (!data) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Trust enrichi */}
      <TrustBreakdownCard data={data} />
      {/* Sentiment */}
      {data.sentiment && <SentimentBadge data={data.sentiment} />}
    </div>
  );
}
