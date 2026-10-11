import { StatusDot } from "./ui";

export interface BackendAvailability {
  state: "checking" | "online" | "offline" | "partial_models" | "no_models";
  ollama: boolean | null;
}

export default function StatusBadge({ availability }: { availability: BackendAvailability }) {
  const { state, ollama } = availability;

  const statusText =
    state === "online"
      ? "Online"
      : state === "partial_models"
      ? "Limited"
      : state === "no_models"
      ? "No models"
      : state === "checking"
      ? "Checking"
      : "Offline";

  return (
    <div className="flex items-center gap-3 lg:gap-4 shrink-0">
      <span
        className="flex items-center gap-1.5 sm:gap-2"
        title={state === "online" ? "API online" : state === "checking" ? "Checking API" : "Analysis unavailable"}
      >
        <StatusDot
          tone={state === "online" ? "ok" : state === "checking" ? "mute" : "danger"}
          pulse={state === "online"}
        />
        <span className="mono-label !text-[9.5px] sm:!text-[10.5px] text-fg-mute">
          <span className="hidden xs:inline">API </span>
          {statusText}
        </span>
      </span>
      {ollama !== null && (
        <span
          className="hidden xl:flex items-center gap-2"
          title={ollama ? "Ollama ready" : "Ollama offline — heuristic explanations"}
        >
          <StatusDot tone={ollama ? "ok" : "mute"} />
          <span className="mono-label text-fg-mute">Analyst {ollama ? "Ready" : "Offline"}</span>
        </span>
      )}
    </div>
  );
}
