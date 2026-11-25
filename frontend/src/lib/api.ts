// NEW_X1 FastAPI client
import type {
  AnalystReport,
  GenerateResponse,
  HealthStatus,
  MatchSquads,
  TeamsResponse,
} from "./types";
import { getAuthClient, sessionHeaders } from "./auth";

// A manual address from Settings wins; otherwise the address the backend
// launcher published to Supabase; otherwise the build-time address.
const SAVED_API_BASE = "new_x1_api_base";
const DISCOVERED_API_BASE = "new_x1_api_discovered";

// The session token is sent to this address, so only the tunnel hosts the
// launcher uses (run_all.py), the configured build address and localhost are accepted.
const TUNNEL_HOST_SUFFIXES = [".trycloudflare.com", ".lhr.life", ".localhost.run"];

function isAllowedBackend(parsed: URL): boolean {
  const local = ["localhost", "127.0.0.1"].includes(parsed.hostname);
  if (local) return parsed.protocol === "http:" || parsed.protocol === "https:";
  if (parsed.protocol !== "https:") return false;
  const configured = process.env.NEXT_PUBLIC_API_BASE?.trim();
  if (configured) {
    try { if (new URL(configured).host === parsed.host) return true; } catch { /* ignore a malformed build value */ }
  }
  return TUNNEL_HOST_SUFFIXES.some((suffix) => parsed.hostname.endsWith(suffix));
}

function readAllowed(key: string): string | null {
  const value = window.localStorage.getItem(key);
  if (!value) return null;
  try {
    const parsed = new URL(value);
    if (isAllowedBackend(parsed) && parsed.pathname === "/") return parsed.origin;
  } catch { /* drop an unreadable value below */ }
  window.localStorage.removeItem(key);
  return null;
}

export function getManualApiBase(): string | null {
  return typeof window === "undefined" ? null : readAllowed(SAVED_API_BASE);
}

export function getDiscoveredApiBase(): string | null {
  return typeof window === "undefined" ? null : readAllowed(DISCOVERED_API_BASE);
}

export function getApiBase(): string {
  if (typeof window !== "undefined") {
    const chosen = readAllowed(SAVED_API_BASE) ?? readAllowed(DISCOVERED_API_BASE);
    if (chosen) return chosen;
  }
  const configured = process.env.NEXT_PUBLIC_API_BASE?.trim();
  if (configured) return configured.replace(/\/$/, "");
  if (typeof window !== "undefined" && ["localhost", "127.0.0.1"].includes(window.location.hostname)) {
    return "http://localhost:8000";
  }
  throw new Error("The analysis server is offline.");
}

let discovery: Promise<void> | null = null;

async function discover(): Promise<void> {
  const client = getAuthClient();
  if (!client) return;
  const { data, error } = await client.from("backend_endpoint").select("url").eq("id", 1).maybeSingle();
  if (error) return;
  const before = window.localStorage.getItem(DISCOVERED_API_BASE);
  let next: string | null = null;
  if (typeof data?.url === "string") {
    try {
      const parsed = new URL(data.url);
      if (isAllowedBackend(parsed) && parsed.pathname === "/") next = parsed.origin;
    } catch { /* ignore an unreadable published value */ }
  }
  if (next) window.localStorage.setItem(DISCOVERED_API_BASE, next);
  else window.localStorage.removeItem(DISCOVERED_API_BASE);
  if (before !== next) window.dispatchEvent(new Event("new_x1_api_base_changed"));
}

/** Look up the published address once per page load, or again after `rediscoverApiBase`. */
async function apiBase(): Promise<string> {
  if (typeof window !== "undefined" && !getManualApiBase()) {
    discovery ??= discover().catch(() => undefined);
    await discovery;
  }
  return getApiBase();
}

/** Called when the backend stops answering, so a restarted laptop's new address is found. */
export function rediscoverApiBase(): void {
  discovery = null;
}

export function saveApiBase(value: string): string {
  const parsed = new URL(value.trim());
  if (parsed.username || parsed.password || parsed.search || parsed.hash || parsed.pathname !== "/") {
    throw new Error("Enter only the server origin, without a path or credentials.");
  }
  if (!isAllowedBackend(parsed)) {
    throw new Error("Use the HTTPS tunnel address printed by the backend launcher, or localhost.");
  }
  const origin = parsed.origin;
  window.localStorage.setItem(SAVED_API_BASE, origin);
  window.dispatchEvent(new Event("new_x1_api_base_changed"));
  return origin;
}

export function clearManualApiBase(): void {
  window.localStorage.removeItem(SAVED_API_BASE);
  rediscoverApiBase();
  window.dispatchEvent(new Event("new_x1_api_base_changed"));
}

export async function getMatches(): Promise<{ matches: import("./types").Match[]; warning: string | null }> {
  return handle(await fetch(`${await apiBase()}/matches`, { cache: "no-store", signal: AbortSignal.timeout(8000) }));
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
  const res = await fetch(`${await apiBase()}/health`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
  return handle<HealthStatus>(res);
}

export async function getMatchSquads(matchId: string | number): Promise<MatchSquads> {
  const res = await fetch(`${await apiBase()}/match_squads?match_id=${encodeURIComponent(String(matchId))}`, { cache: "no-store" });
  return handle<MatchSquads>(res);
}

export async function getTeams(): Promise<TeamsResponse> {
  const res = await fetch(`${await apiBase()}/teams`, { cache: "no-store" });
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
  const res = await fetch(`${await apiBase()}/generate_best_team`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...await sessionHeaders() },
    signal: AbortSignal.timeout(120000),
    body: JSON.stringify(req),
  });
  return handle<GenerateResponse>(res);
}

export async function explainTeam(explainToken: string): Promise<AnalystReport> {
  const res = await fetch(`${await apiBase()}/explain_team`, {
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
  return handle<SavedAnalysis>(await fetch(`${await apiBase()}/analyses`, {
    method: "POST", headers: { "Content-Type": "application/json", ...await sessionHeaders() },
    signal: AbortSignal.timeout(15000), body: JSON.stringify({ explain_token: explainToken, title }),
  }));
}

export async function getSavedAnalyses(): Promise<{ analyses: SavedAnalysis[] }> {
  return handle(await fetch(`${await apiBase()}/analyses`, { cache: "no-store",
    headers: await sessionHeaders(), signal: AbortSignal.timeout(15000) }));
}

export async function deleteSavedAnalysis(id: string): Promise<void> {
  await handle(await fetch(`${await apiBase()}/analyses/${encodeURIComponent(id)}`, {
    method: "DELETE", headers: await sessionHeaders(), signal: AbortSignal.timeout(15000),
  }));
}
