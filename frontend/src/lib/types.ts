// NEW_X1 — Shared API types

export interface Match {
  match_id: number | string;
  series: string;
  team1: string;
  team2: string;
  match_type: string;
  venue: string;
  date: string;
  status: string;
  has_squad?: boolean;
  squad_source?: "provider" | "last_match" | "pending";
  squad_match_dates?: Record<string, string>;
  match_ended?: boolean;
}

export type Role = "WK" | "BAT" | "AR" | "BOWL";

export interface PlayerEntry {
  display_name: string;
  fantasy_key: string;
  role: Role;
  role_source?: string;
  team: string;
  engine: "ml" | "recent_form" | "league_prior";
  base_score: number;
  pitch_multiplier: number;
  weather_multiplier?: number;
  bowling_style?: string;
  injury_status: string;
  injury_multiplier: number;
  playing_probability: number | null;
  availability_factor: number;
  selection_status: "unconfirmed" | "confirmed";
  adjusted_score: number;
  std: number;
  ci_low: number;
  ci_high: number;
  captain_upside: number;
  matches_played: number;
  name_match?: string | null;
  injury_news?: string;
}

export interface Weather {
  available?: boolean;
  date?: string;
  temperature_c: number;
  humidity_pct: number;
  cloud_cover_pct: number;
  wind_speed_kmh: number;
  seam_swing_advantage: boolean;
  dew_risk: boolean;
  summary: string;
}

export interface PitchProfile {
  category: string;
  avg_1st_innings: number | null;
  boundary_pct: number | null;
  source: "historical" | "curated_prior" | "unavailable";
  format: string;
  sample_size: number | null;
  batter_mult: number;
  pacer_mult: number;
  spinner_mult: number;
  description: string;
  bowling_bias?: string;
  confidence?: "low" | "moderate";
  scoring_vs_peers_pct?: number;
  wickets_vs_peers_pct?: number;
  as_of?: string;
  snapshot_latest_match?: string;
  snapshot_fallback?: boolean;
  last5?: PitchWindow;
  last10?: PitchWindow;
  style_evidence?: { pace: { balls: number }; spin: { balls: number } };
}

export interface PitchWindow {
  matches: number;
  same_format_matches: number;
  avg_1st_innings: number | null;
  wickets_per_innings: number | null;
  defended: number;
  decided_limited_overs: number;
  low_total_defences: number;
  runs_per_over: number | null;
  boundary_pct: number | null;
  from_date: string | null;
  to_date: string | null;
}

export interface GenerationSummary {
  expected_total_points: number;
  role_counts: Record<Role, number>;
  team_split: Record<string, number>;
  captain: string | null;
  vice_captain: string | null;
  solver_status: string;
  constraint_mode: "strict" | "relaxed_team" | "relaxed_roles";
  squad_size: number;
  engine: string;
  league_prior: number;
}

export interface GenerateResponse {
  request: {
    match_id: number | string | null;
    team1: string | null;
    team2: string | null;
    format: string;
    date: string;
    venue: string;
    use_ml: boolean;
    use_intelligence: boolean;
    risk_aversion: number;
    mode: "prediction" | "retrospective";
  };
  best_team: PlayerEntry[];
  bench: PlayerEntry[];
  summary: GenerationSummary;
  intelligence: {
    enabled: boolean;
    weather: Weather | null;
    pitch: PitchProfile | null;
    news_scan_used: boolean;
  };
  name_resolution: { resolved: number; unresolved: string[] };
  validation: { valid: boolean; violations: string[] };
  data_provenance: {
    model: string;
    features: string;
    fantasy: string;
    fixtures: string;
    squads: string;
    warnings: string[];
  };
  explain_token: string;
}

export interface MatchSquads {
  match_id: string;
  team1: string;
  team2: string;
  venue: string;
  date: string;
  format: string;
  squad_source?: "provider" | "last_match";
  squad_match_dates?: Record<string, string> | null;
  team1_squad: SquadPlayer[];
  team2_squad: SquadPlayer[];
}

export interface SquadPlayer {
  display_name: string;
  fantasy_key: string | null;
  name_match: string | null;
  role: Role | null;
  injury_status: string;
  team: string;
}

export interface AnalystDriver {
  feature: string;
  label: string;
  impact: number;
}

export interface AnalystReport {
  generated_with: "ollama" | "heuristic";
  attribution: { method: string; available: boolean; covered_selected: number; selected_count: number };
  team_report: string;
  players: {
    display_name: string;
    role: Role;
    team: string;
    selected: boolean;
    adjusted_score: number;
    explanation: string;
    drivers: AnalystDriver[];
  }[];
  context: {
    venue: string;
    date: string;
    format: string;
    constraint_mode: string;
    pitch_category: string;
    weather_summary: string;
    expected_total_points: number;
  };
}

export interface HealthStatus {
  status: string;
  models: Record<string, boolean>;
  ollama: boolean;
  sources?: Record<string, Record<string, string>>;
  fixtures?: { source: string | null; fetched_at: string | null; fallback_used: boolean; warning: string | null };
  squads?: { fetched_at: string | null; fallback_used: boolean; warning: string | null };
}

export interface TeamsResponse {
  teams: string[];
  venues: string[];
}
