// NEW_X1 — FastAPI client
import type {
  AnalystReport,
  GenerateResponse,
  HealthStatus,
  MatchSquads,
  TeamsResponse,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

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
  const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
  return handle<HealthStatus>(res);
}

export async function getMatchSquads(matchId: string | number): Promise<MatchSquads> {
  const res = await fetch(`${API_BASE}/match_squads?match_id=${matchId}`, { cache: "no-store" });
  return handle<MatchSquads>(res);
}

export async function getTeams(): Promise<TeamsResponse> {
  const res = await fetch(`${API_BASE}/teams`, { cache: "no-store" });
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
}

export async function generateBestTeam(req: GenerateRequest): Promise<GenerateResponse> {
  const res = await fetch(`${API_BASE}/generate_best_team`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handle<GenerateResponse>(res);
}

export async function explainTeam(explainToken: string): Promise<AnalystReport> {
  const res = await fetch(`${API_BASE}/explain_team`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ explain_token: explainToken }),
  });
  return handle<AnalystReport>(res);
}
