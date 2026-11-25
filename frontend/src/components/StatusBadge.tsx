import { StatusDot } from "./ui";

export interface BackendAvailability {
  state: "checking" | "online" | "offline" | "partial_models" | "no_models";
  ollama: boolean | null;
}

const LABELS: Record<BackendAvailability["state"], string> = {
  online: "Online",
  partial_models: "Limited",
  no_models: "Loading models",
  checking: "Checking",
  offline: "Offline",
};

export default function StatusBadge({ availability }: { availability: BackendAvailability }) {
  const { state, ollama } = availability;
  const tone = state === "online" ? "ok" : state === "checking" ? "mute" : state === "offline" ? "danger" : "warn";

  return (
    <span
      className="flex items-center gap-2 shrink-0 text-sm text-fg-dim"
      title={ollama === null ? undefined : ollama ? "Written analyst reports available" : "Analyst reports use the rule-based fallback"}
    >
      <StatusDot tone={tone} />
      {LABELS[state]}
    </span>
  );
}
