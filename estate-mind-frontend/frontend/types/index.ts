// ─── Annonce ──────────────────────────────────────────────────────────────────
export interface Listing {
  id?: number;
  title?: string;
  description: string;
  price: number;
  surface: number;
  city: string;
  property_type: string;
  source: string;
  governorate?: string;
  rooms?: number;
  trust_score?: number;
  trust_level?: TrustLevel;
  legal_risk_score?: number;
  url?: string;
}

// ─── Scoring ──────────────────────────────────────────────────────────────────
export type TrustLevel  = "Fiable" | "Moyen" | "Suspect";
export type LegalLevel  = "Faible" | "Moyen" | "Élevé";
export type Verdict     = "FAVORABLE" | "ATTENTION" | "DANGER";

export interface RelevantLaw {
  article: string;
  source: string;
  summary: string;
}

export interface AnalyzeResult {
  trust_score:       number;
  trust_level:       TrustLevel;
  legal_risk_score:  number;
  legal_risk_level:  LegalLevel;
  fraud_flags:       string[];
  legal_flags:       string[];
  relevant_laws:     RelevantLaw[];
  price_analysis:    string;
  recommendation:    string;
  verdict:           Verdict;
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
export interface DashboardStats {
  total_raw:      number;
  total_clean:    number;
  avg_trust:      number;
  suspect_count:  number;
  high_legal:     number;
  recent:         RecentAnalysis[];
}

export interface RecentAnalysis {
  id:           number;
  title:        string;
  city:         string;
  type:         string;
  trust:        number;
  legal:        number;
  trust_level:  TrustLevel;
  legal_level:  LegalLevel;
}

// ─── Marché ───────────────────────────────────────────────────────────────────
export interface MarketStat {
  city:    string;
  ppm2:    number;
  n:       number;
  median:  number;
  mean:    number;
}

export interface MarketOverview {
  total:          number;
  median_ppm2:    number;
  mean_ppm2:      number;
  top_city:       string;
  cities:         MarketStat[];
  property_types: Record<string, number>;
}

// ─── Pipeline ─────────────────────────────────────────────────────────────────
export interface PipelineReport {
  rows_in:          number;
  rows_out:         number;
  mean_trust:       number;
  suspect_count:    number;
  high_legal:       number;
  medium_legal:     number;
  low_legal:        number;
  output_path:      string;
}

export interface SystemStatus {
  dataset_available: boolean;
  dataset_rows:      number;
  trust_scored:      boolean;
  legal_scored:      boolean;
  vector_store:      boolean;
}

// ─── API Response ──────────────────────────────────────────────────────────────
export interface ApiResponse<T> {
  data:    T;
  success: boolean;
  error?:  string;
}
