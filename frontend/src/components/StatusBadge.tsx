"use client";

import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";
import { StatusDot } from "./ui";

export default function StatusBadge() {
  const [health, setHealth] = useState<{
    models: Record<string, boolean> | null;
    ollama: boolean | null;
  }>({ models: null, ollama: null });

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const h = await getHealth();
        if (!cancelled) setHealth({ models: h.models, ollama: h.ollama });
      } catch {
        if (!cancelled) setHealth({ models: null, ollama: null });
      }
    };
    check();
    const t = setInterval(check, 60_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  const apiUp = health.models !== null;
  const modelsUp = health.models ? Object.values(health.models).some(Boolean) : false;

  return (
    <div className="hidden sm:flex items-center gap-4">
      <span className="flex items-center gap-2" title={apiUp && modelsUp ? "API online" : "API unreachable"}>
        <StatusDot tone={apiUp && modelsUp ? "ok" : "danger"} pulse={apiUp && modelsUp} />
        <span className="mono-label text-fg-mute">API {apiUp ? (modelsUp ? "Online" : "No models") : "Offline"}</span>
      </span>
      {health.ollama !== null && (
        <span className="hidden lg:flex items-center gap-2" title={health.ollama ? "Ollama ready" : "Ollama offline — heuristic explanations"}>
          <StatusDot tone={health.ollama ? "ok" : "mute"} />
          <span className="mono-label text-fg-mute">Analyst {health.ollama ? "Ready" : "Offline"}</span>
        </span>
      )}
    </div>
  );
}
