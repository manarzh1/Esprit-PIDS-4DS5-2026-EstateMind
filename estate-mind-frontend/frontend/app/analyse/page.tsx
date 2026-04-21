"use client";
import { useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { Gauge } from "@/components/Gauge";
import { Badge } from "@/components/Badge";
import { analyzeListing } from "@/lib/api";
import type { AnalyzeResult, Verdict } from "@/types";

const TC = (s: number) => s >= .75 ? "var(--ok)" : s >= .5 ? "var(--warn)" : "var(--bad)";
const LC = (s: number) => s <  .3  ? "var(--ok)" : s <  .6 ? "var(--warn)" : "var(--bad)";

const VERDICT_BG: Record<Verdict, string> = {
  FAVORABLE: "rgba(82,200,150,.08)",
  ATTENTION: "rgba(232,168,76,.08)",
  DANGER:    "rgba(224,92,92,.08)",
};
const VERDICT_BORDER: Record<Verdict, string> = {
  FAVORABLE: "rgba(82,200,150,.28)",
  ATTENTION: "rgba(232,168,76,.28)",
  DANGER:    "rgba(224,92,92,.28)",
};

const PROPERTY_TYPES = ["appartement","villa","maison","terrain","studio","bureau_local","immeuble","ferme"];
const SOURCES        = ["particulier","tayara","mubawab","remax","tecnocasa","century21","darkom"];

export default function AnalysePage() {
  const [form, setForm] = useState({
    description:"", price:"", surface:"", city:"",
    property_type:"appartement", source:"particulier",
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult]   = useState<AnalyzeResult | null>(null);
  const [error, setError]     = useState<string | null>(null);

  const up = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  const canSubmit = !loading && form.description && form.price && form.city;

  const analyze = async () => {
    setLoading(true); setResult(null); setError(null);
    try {
      const data = await analyzeListing({
        description:   form.description,
        price:         Number(form.price),
        surface:       Number(form.surface) || 0,
        city:          form.city,
        property_type: form.property_type,
        source:        form.source,
      });
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur d'analyse. Vérifiez que le backend est lancé.");
    }
    setLoading(false);
  };

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:8, marginBottom:8 }}>
      <div style={{ marginBottom:16 }}>
        <h1 style={{ fontFamily:"var(--font-display)", fontSize:24, fontWeight:600, marginBottom:4 }}>Analyser une annonce</h1>
        <p style={{ fontSize:13, color:"var(--mut)" }}>Évaluation trust score + risque juridique via IA</p>
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:20, alignItems:"start" }}>
        {/* ── Formulaire ───────────────────────────────────────────────────── */}
        <div className="card" style={{ padding:24 }}>
          <div style={{ fontFamily:"var(--font-display)", fontSize:16, fontWeight:600, marginBottom:22 }}>
            Informations de l'annonce
          </div>
          <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
              <div>
                <label style={{ fontSize:11, color:"var(--mut)", textTransform:"uppercase", letterSpacing:".06em", display:"block", marginBottom:6 }}>
                  Type de bien
                </label>
                <select value={form.property_type} onChange={e => up("property_type", e.target.value)}>
                  {PROPERTY_TYPES.map(t => <option key={t} value={t}>{t.replace("_"," ")}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize:11, color:"var(--mut)", textTransform:"uppercase", letterSpacing:".06em", display:"block", marginBottom:6 }}>
                  Ville
                </label>
                <input value={form.city} onChange={e => up("city", e.target.value)} placeholder="Ex: Tunis, Hammamet..." />
              </div>
            </div>

            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
              <div>
                <label style={{ fontSize:11, color:"var(--mut)", textTransform:"uppercase", letterSpacing:".06em", display:"block", marginBottom:6 }}>
                  Prix (TND)
                </label>
                <input type="number" value={form.price} onChange={e => up("price", e.target.value)} placeholder="Ex: 280 000" />
              </div>
              <div>
                <label style={{ fontSize:11, color:"var(--mut)", textTransform:"uppercase", letterSpacing:".06em", display:"block", marginBottom:6 }}>
                  Surface (m²)
                </label>
                <input type="number" value={form.surface} onChange={e => up("surface", e.target.value)} placeholder="Ex: 120" />
              </div>
            </div>

            <div>
              <label style={{ fontSize:11, color:"var(--mut)", textTransform:"uppercase", letterSpacing:".06em", display:"block", marginBottom:6 }}>
                Source
              </label>
              <select value={form.source} onChange={e => up("source", e.target.value)}>
                {SOURCES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>

            <div>
              <label style={{ fontSize:11, color:"var(--mut)", textTransform:"uppercase", letterSpacing:".06em", display:"block", marginBottom:6 }}>
                Description de l'annonce
              </label>
              <textarea
                value={form.description}
                onChange={e => up("description", e.target.value)}
                placeholder="Collez ici le texte complet de l'annonce..."
                rows={6}
                style={{ resize:"vertical", lineHeight:1.6 }}
              />
            </div>

            <button className="btn-gold" onClick={analyze} disabled={!canSubmit}>
              {loading
                ? <><Loader2 size={14} className="animate-spin" /> Analyse en cours...</>
                : <><Sparkles size={14} /> Analyser cette annonce</>
              }
            </button>
          </div>
        </div>

        {/* ── Résultats ────────────────────────────────────────────────────── */}
        <div>
          {!result && !loading && (
            <div className="card" style={{ padding:48, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:16, minHeight:420, textAlign:"center" }}>
              <div style={{ width:52, height:52, borderRadius:13, background:"var(--gdim)", display:"flex", alignItems:"center", justifyContent:"center", fontSize:22 }}>
                🔍
              </div>
              <div>
                <div style={{ fontFamily:"var(--font-display)", fontSize:16, fontWeight:600, marginBottom:8 }}>
                  Remplissez le formulaire
                </div>
                <div style={{ fontSize:13, color:"var(--mut)", lineHeight:1.6 }}>
                  L'IA analysera le trust score,<br />le risque juridique et les signaux d'alerte.
                </div>
              </div>
            </div>
          )}

          {loading && (
            <div className="card" style={{ padding:48, display:"flex", flexDirection:"column", alignItems:"center", gap:20, minHeight:420, justifyContent:"center" }}>
              <div className="animate-spin" style={{ width:48, height:48, border:"2px solid var(--gbor)", borderTop:"2px solid var(--gold)", borderRadius:"50%" }} />
              <div style={{ fontSize:13, color:"var(--mut)" }}>Analyse en cours...</div>
            </div>
          )}

          {error && (
            <div style={{ background:"rgba(224,92,92,.08)", border:"1px solid rgba(224,92,92,.25)", borderRadius:12, padding:16, fontSize:13, color:"var(--bad)", marginBottom:14 }}>
              {error}
            </div>
          )}

          {result && (
            <div className="animate-fadeup" style={{ display:"flex", flexDirection:"column", gap:14 }}>
              {/* Verdict */}
              <div style={{ background:VERDICT_BG[result.verdict], border:`1px solid ${VERDICT_BORDER[result.verdict]}`, borderRadius:12, padding:"16px 22px", display:"flex", alignItems:"center", justifyContent:"space-between" }}>
                <span style={{ fontFamily:"var(--font-display)", fontSize:15, fontWeight:600 }}>Verdict final</span>
                <Badge level={result.verdict} />
              </div>

              {/* Gauges */}
              <div className="card" style={{ padding:22, display:"flex", justifyContent:"space-around", alignItems:"center" }}>
                <Gauge score={result.trust_score}         label="Trust Score"     color={TC(result.trust_score)}         />
                <div style={{ width:1, height:72, background:"var(--bor)" }} />
                <Gauge score={1 - result.legal_risk_score} label="Sécurité légale" color={LC(result.legal_risk_score)}    />
              </div>

              {/* Flags */}
              {[...(result.fraud_flags ?? []), ...(result.legal_flags ?? [])].length > 0 && (
                <div className="card" style={{ padding:20 }}>
                  <div className="section-title" style={{ marginBottom:12 }}>Signaux d'alerte</div>
                  {[...(result.fraud_flags ?? []), ...(result.legal_flags ?? [])].map((f, i) => (
                    <div key={i} style={{ display:"flex", alignItems:"flex-start", gap:9, padding:"8px 0", borderBottom:"1px solid var(--bor)" }}>
                      <span style={{ fontSize:14, marginTop:1 }}>⚠</span>
                      <span style={{ fontSize:13, lineHeight:1.5 }}>{f}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Lois applicables */}
              {result.relevant_laws?.length > 0 && (
                <div className="card" style={{ padding:20 }}>
                  <div className="section-title" style={{ marginBottom:14 }}>Lois applicables</div>
                  {result.relevant_laws.map((l, i) => (
                    <div key={i} style={{ borderLeft:"2px solid var(--gbor)", paddingLeft:13, marginBottom:12 }}>
                      <div style={{ fontSize:11, color:"var(--gold)", marginBottom:3 }}>{l.article} — {l.source}</div>
                      <div style={{ fontSize:12, color:"var(--mut)", lineHeight:1.5 }}>{l.summary}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Prix */}
              <div style={{ background:"rgba(107,159,232,.08)", border:"1px solid rgba(107,159,232,.22)", borderRadius:10, padding:"13px 16px" }}>
                <div style={{ fontSize:11, color:"var(--info)", textTransform:"uppercase", letterSpacing:".06em", marginBottom:4 }}>Analyse du prix</div>
                <div style={{ fontSize:13, lineHeight:1.5 }}>{result.price_analysis}</div>
              </div>

              {/* Recommandation */}
              <div style={{ background:"var(--gdim)", border:"1px solid var(--gbor)", borderRadius:10, padding:"14px 18px" }}>
                <div style={{ fontSize:11, color:"var(--gold)", textTransform:"uppercase", letterSpacing:".06em", marginBottom:6 }}>Recommandation</div>
                <div style={{ fontSize:13, lineHeight:1.6 }}>{result.recommendation}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
