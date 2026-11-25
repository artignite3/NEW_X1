import type { Role } from "@/lib/types";

export const ROLE_LABELS: Record<Role, string> = {
  WK: "Wicketkeeper",
  BAT: "Batter",
  AR: "All-rounder",
  BOWL: "Bowler",
};

// Role is information, not decoration: shown as muted text, never a color
export const ROLE_SHORT: Record<Role, string> = {
  WK: "WK",
  BAT: "Bat",
  AR: "AR",
  BOWL: "Bowl",
};

export const ENGINE_LABELS: Record<string, string> = {
  ml: "Model",
  recent_form: "Recent form",
  league_prior: "League average",
};
