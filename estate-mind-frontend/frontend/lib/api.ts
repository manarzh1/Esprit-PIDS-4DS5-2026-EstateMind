/**
 * Estate Mind — API Client
 * Toutes les fonctions qui parlent au backend FastAPI (localhost:8000)
 * Le next.config.mjs rewrite `/api/*` → `http://localhost:8000/api/*`
 */
import type {
  AnalyzeResult, DashboardStats, MarketOverview,
  PipelineReport, SystemStatus,
} from "@/types";

const BASE = "/api";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ─── Status ───────────────────────────────────────────────────────────────────
export async function getStatus(): Promise<SystemStatus> {
  return fetchJson(`${BASE}/status`);
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
export async function getDashboard(): Promise<DashboardStats> {
  return fetchJson(`${BASE}/dashboard`);
}

// ─── Analyser une annonce ─────────────────────────────────────────────────────
export interface AnalyzePayload {
  description:   string;
  price:         number;
  surface:       number;
  city:          string;
  property_type: string;
  source:        string;
}

export async function analyzeListing(payload: AnalyzePayload): Promise<AnalyzeResult> {
  return fetchJson(`${BASE}/analyze`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ─── Marché ───────────────────────────────────────────────────────────────────
export async function getMarket(
  city?: string,
  property_type?: string,
): Promise<MarketOverview> {
  const params = new URLSearchParams();
  if (city)          params.set("city", city);
  if (property_type) params.set("property_type", property_type);
  return fetchJson(`${BASE}/market?${params}`);
}

// ─── Pipeline ─────────────────────────────────────────────────────────────────
export async function runPipeline(csv_path?: string): Promise<PipelineReport> {
  return fetchJson(`${BASE}/pipeline`, {
    method: "POST",
    body: JSON.stringify({ csv_path: csv_path ?? "" }),
  });
}

// ─── SSE : logs du pipeline en streaming ─────────────────────────────────────
export function streamPipelineLogs(
  onMessage: (line: string) => void,
  onDone: () => void,
): () => void {
  const es = new EventSource(`${BASE}/pipeline/stream`);
  es.onmessage = (e) => {
    if (e.data === "[DONE]") { onDone(); es.close(); }
    else onMessage(e.data);
  };
  es.onerror = () => { onDone(); es.close(); };
  return () => es.close();
}
