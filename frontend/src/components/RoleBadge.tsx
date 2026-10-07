import type { Role } from "@/lib/types";

export const ROLE_LABELS: Record<Role, string> = {
  WK: "Wicketkeeper",
  BAT: "Batter",
  AR: "All-rounder",
  BOWL: "Bowler",
};

// Restrained supporting tones — role is informational, not decorative
export const ROLE_TONES: Record<Role, string> = {
  WK: "text-warn border-warn/40",
  BAT: "text-accent border-accent/40",
  AR: "text-ok border-ok/40",
  BOWL: "text-[#6ea3d8] border-[#6ea3d8]/40",
};

export const ENGINE_LABELS: Record<string, { label: string; tone: string }> = {
  ml: { label: "TriBE ML", tone: "text-fg-dim border-line" },
  recent_form: { label: "Recent Form", tone: "text-fg-dim border-line" },
  league_prior: { label: "League Prior", tone: "text-fg-mute border-line-soft" },
};
