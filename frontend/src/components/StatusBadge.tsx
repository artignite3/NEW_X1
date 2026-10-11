import { StatusDot } from "./ui";

export interface BackendAvailability {
  state: "checking" | "online" | "offline" | "partial_models" | "no_models";
  ollama: boolean | null;
}

export default function StatusBadge({ availability }: { availability: BackendAvailability }) {
  const { state, ollama } = availability;

  return (
    <div className="hidden sm:flex items-center gap-4">
      <span className="flex items-center gap-2" title={state === "online" ? "API online" : state === "checking" ? "Checking API" : "Analysis unavailable"}>
        <StatusDot tone={state === "online" ? "ok" : state === "checking" ? "mute" : "danger"} pulse={state === "online"} />
        <span className="mono-label text-fg-mute">API {state === "online" ? "Online" : state === "partial_models" ? "Limited" : state === "no_models" ? "No models" : state === "checking" ? "Checking" : "Offline"}</span>
      </span>
      {ollama !== null && (
        <span className="hidden lg:flex items-center gap-2" title={ollama ? "Ollama ready" : "Ollama offline — heuristic explanations"}>
          <StatusDot tone={ollama ? "ok" : "mute"} />
          <span className="mono-label text-fg-mute">Analyst {ollama ? "Ready" : "Offline"}</span>
        </span>
      )}
    </div>
  );
}
