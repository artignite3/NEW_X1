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
  playing_probability: number;
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
  avg_1st_innings: number;
  boundary_pct: number;
  batter_mult: number;
  pacer_mult: number;
  spinner_mult: number;
  description: string;
}

export interface GenerationSummary {
  expected_total_points: number;
  role_counts: Record<Role, number>;
  team_split: Record<string, number>;
  captain: string | null;
  vice_captain: string | null;
  solver_status: string;
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
  explain_token: string;
}

export interface MatchSquads {
  match_id: string;
  team1: string;
  team2: string;
  venue: string;
  date: string;
  format: string;
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
    pitch_category: string;
    weather_summary: string;
    expected_total_points: number;
  };
}

export interface HealthStatus {
  status: string;
  models: Record<string, boolean>;
  ollama: boolean;
}

export interface TeamsResponse {
  teams: string[];
  venues: string[];
}
