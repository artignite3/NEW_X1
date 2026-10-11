// NEW_X1 — FastAPI client
import type {
  AnalystReport,
  GenerateResponse,
  HealthStatus,
  MatchSquads,
  TeamsResponse,
} from "./types";
import { sessionHeaders } from "./auth";

const SAVED_API_BASE = "new_x1_api_base";

export function getApiBase(): string {
  if (typeof window !== "undefined") {
    const saved = window.localStorage.getItem(SAVED_API_BASE);
    if (saved) return saved;
  }
  const configured = process.env.NEXT_PUBLIC_API_BASE?.trim();
  if (configured) return configured.replace(/\/$/, "");
  if (typeof window !== "undefined" && ["localhost", "127.0.0.1"].includes(window.location.hostname)) {
    return "http://localhost:8000";
  }
  throw new Error("Backend address is missing. Open Settings and connect the local backend.");
}

export function saveApiBase(value: string): string {
  const parsed = new URL(value.trim());
  const local = ["localhost", "127.0.0.1"].includes(parsed.hostname);
  if (parsed.protocol !== "https:" && !(local && parsed.protocol === "http:")) {
    throw new Error("Use an HTTPS backend address, or HTTP on localhost.");
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash || parsed.pathname !== "/") {
    throw new Error("Enter only the backend origin, without a path or credentials.");
  }
  const origin = parsed.origin;
  window.localStorage.setItem(SAVED_API_BASE, origin);
  window.dispatchEvent(new Event("new_x1_api_base_changed"));
  return origin;
}

export async function getMatches(): Promise<{ matches: import("./types").Match[]; warning: string | null }> {
  return handle(await fetch(`${getApiBase()}/matches`, { cache: "no-store", signal: AbortSignal.timeout(8000) }));
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `API error ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function getHealth(): Promise<HealthStatus> {
  const res = await fetch(`${getApiBase()}/health`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
  return handle<HealthStatus>(res);
}

export async function getMatchSquads(matchId: string | number): Promise<MatchSquads> {
  const res = await fetch(`${getApiBase()}/match_squads?match_id=${matchId}`, { cache: "no-store" });
  return handle<MatchSquads>(res);
}

export async function getTeams(): Promise<TeamsResponse> {
  const res = await fetch(`${getApiBase()}/teams`, { cache: "no-store" });
  return handle<TeamsResponse>(res);
}

export interface GenerateRequest {
  match_id?: string | number;
  team1?: string;
  team2?: string;
  format?: string;
  venue?: string;
  date?: string;
  use_ml?: boolean;
  use_intelligence?: boolean;
  risk_aversion?: number;
  scan_news?: boolean;
  mode?: "prediction" | "retrospective";
  allow_relaxation?: boolean;
}

export async function generateBestTeam(req: GenerateRequest): Promise<GenerateResponse> {
  const res = await fetch(`${getApiBase()}/generate_best_team`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...await sessionHeaders() },
    signal: AbortSignal.timeout(120000),
    body: JSON.stringify(req),
  });
  return handle<GenerateResponse>(res);
}

export async function explainTeam(explainToken: string): Promise<AnalystReport> {
  const res = await fetch(`${getApiBase()}/explain_team`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...await sessionHeaders() },
    signal: AbortSignal.timeout(120000),
    body: JSON.stringify({ explain_token: explainToken }),
  });
  return handle<AnalystReport>(res);
}

export interface SavedAnalysis {
  id: string;
  created_at: string;
  payload: { title: string; result: GenerateResponse };
}

export async function saveAnalysis(explainToken: string, title: string): Promise<SavedAnalysis> {
  return handle<SavedAnalysis>(await fetch(`${getApiBase()}/analyses`, {
    method: "POST", headers: { "Content-Type": "application/json", ...await sessionHeaders() },
    signal: AbortSignal.timeout(15000), body: JSON.stringify({ explain_token: explainToken, title }),
  }));
}

export async function getSavedAnalyses(): Promise<{ analyses: SavedAnalysis[] }> {
  return handle(await fetch(`${getApiBase()}/analyses`, { cache: "no-store",
    headers: await sessionHeaders(), signal: AbortSignal.timeout(15000) }));
}

export async function deleteSavedAnalysis(id: string): Promise<void> {
  await handle(await fetch(`${getApiBase()}/analyses/${encodeURIComponent(id)}`, {
    method: "DELETE", headers: await sessionHeaders(), signal: AbortSignal.timeout(15000),
  }));
}
