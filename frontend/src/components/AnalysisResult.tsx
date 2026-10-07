"use client";

import { useEffect, useRef, useState } from "react";
import type { AnalystReport, GenerateResponse } from "@/lib/types";
import { explainTeam } from "@/lib/api";
import PlayerCard from "./PlayerCard";
import { PitchPanel, WeatherPanel } from "./IntelligencePanels";
import { ROLE_LABELS } from "./RoleBadge";
import { IconAlert, IconCalendar, IconPin, IconShield, IconTarget, IconTerminal, IconUsers } from "./icons";
import { Button, Chip, Panel, Progress, SectionLabel, Skeleton } from "./ui";

// Count-up for the headline projection — restrained, respects reduced motion
function useCountUp(target: number, duration = 700): number {
  const [value, setValue] = useState(target);
  const prev = useRef(target);
  useEffect(() => {
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced || Math.abs(target - prev.current) < 0.5) {
      prev.current = target;
      setValue(target);
      return;
    }
    const from = prev.current;
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(from + (target - from) * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
      else prev.current = target;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return value;
}

export default function AnalysisResult({ result }: Props) {
  const [report, setReport] = useState<AnalystReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  const { request, best_team, bench, summary, intelligence, name_resolution } = result;
  const total = useCountUp(summary.expected_total_points);
  const engineLabel = summary.engine.replace(/\s*\(.*\)$/, ""); // "TriBE Ensemble (…)" -> "TriBE Ensemble"

  const loadReport = async () => {
    setReportLoading(true);
    setReportError(null);
    try {
      setReport(await explainTeam(result.explain_token));
    } catch (e) {
      setReportError(e instanceof Error ? e.message : "Failed to generate report");
    } finally {
      setReportLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* ── Match header ─────────────────────────────────────────────── */}
      <Panel className="p-6 reveal">
        <div className="flex flex-wrap justify-between gap-x-10 gap-y-5">
          <div className="min-w-0">
            <div className="flex items-center gap-2.5 mb-3">
              <SectionLabel accent>Optimal XI</SectionLabel>
              <Chip>{request.format.toUpperCase()}</Chip>
              <Chip tone="accent">{engineLabel}</Chip>
            </div>
            <h2 className="text-[22px] font-semibold text-fg leading-tight">
              {request.team1}
              <span className="text-fg-mute font-normal mx-2.5">vs</span>
              {request.team2}
            </h2>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-fg-mute">
              <span className="inline-flex items-center gap-1.5 text-xs">
                <IconPin size={13} />
                <span className="truncate max-w-xs md:max-w-md">{request.venue}</span>
              </span>
              <span className="inline-flex items-center gap-1.5 text-xs">
                <IconCalendar size={13} />
                <span className="mono-value">{request.date}</span>
              </span>
            </div>
          </div>

          <div className="text-right">
            <div className="mono-value text-4xl leading-none font-medium text-accent tabular-nums">
              {total.toFixed(0)}
            </div>
            <div className="mono-label text-fg-mute mt-1.5">Projected Team Points</div>
            <div className="mt-3 flex items-center justify-end gap-3 text-xs">
              <span className="text-fg-mute">Captain</span>
              <span className="text-fg font-medium">{summary.captain}</span>
              <span className="w-px h-3.5 bg-line" />
              <span className="text-fg-mute">VC</span>
              <span className="text-fg-dim">{summary.vice_captain}</span>
            </div>
          </div>
        </div>

        {/* Instrumentation strip */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-line-soft border border-line-soft rounded-md overflow-hidden mt-5">
          <Metric icon={<IconUsers size={13} />} label="Team Split" value={Object.entries(summary.team_split).map(([t, n]) => `${n} ${t}`).join(" / ")} />
          <Metric icon={<IconShield size={13} />} label="Role Mix" value={(["WK", "BAT", "AR", "BOWL"] as const).filter((r) => summary.role_counts[r] > 0).map((r) => `${summary.role_counts[r]} ${r}`).join(" · ")} />
          <Metric icon={<IconTarget size={13} />} label="Solver" value={`${summary.solver_status} · squad ${summary.squad_size}`} />
          <Metric icon={<IconShield size={13} />} label="Constraints" value={`${summary.constraint_mode.replaceAll("_", " ")} · ${result.validation.valid ? "verified" : "invalid"}`} />
          <Metric icon={<IconTerminal size={13} />} label="Resolution" value={`${name_resolution.resolved}/${summary.squad_size} matched`} />
        </div>
      </Panel>

      {(result.data_provenance.warnings.length > 0 ||
        Object.values(result.data_provenance).some((value) => value === "last_good")) && (
        <div className="flex items-start gap-2.5 text-sm text-warn border border-warn/25 bg-warn/5 rounded-md px-4 py-3">
          <IconAlert size={15} className="shrink-0 mt-0.5" />
          <span>
            {Object.values(result.data_provenance).some((value) => value === "last_good") ? "Using verified backup data. " : "Data warning. "}
            {result.data_provenance.warnings.join(" ")}
          </span>
        </div>
      )}

      {/* ── Intelligence ─────────────────────────────────────────────── */}
      {intelligence.enabled && (intelligence.weather || intelligence.pitch) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {intelligence.weather && (
            <div className="reveal" style={{ animationDelay: "80ms" }}>
              <WeatherPanel weather={intelligence.weather} />
            </div>
          )}
          {intelligence.pitch && (
            <div className="reveal" style={{ animationDelay: "140ms" }}>
              <PitchPanel pitch={intelligence.pitch} />
            </div>
          )}
        </div>
      )}

      {/* ── Selected XI ──────────────────────────────────────────────── */}
      <section className="reveal" style={{ animationDelay: "120ms" }}>
        <div className="flex items-center justify-between mb-3.5">
          <SectionLabel>Selected XI</SectionLabel>
          <span className="mono-label text-fg-mute">{best_team.length} players</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3.5">
          {best_team.map((p, i) => (
            <div key={p.fantasy_key} className="reveal" style={{ animationDelay: `${150 + i * 55}ms` }}>
              <PlayerCard
                player={p}
                rank={i + 1}
                isCaptain={p.display_name === summary.captain}
                isViceCaptain={p.display_name === summary.vice_captain}
              />
            </div>
          ))}
        </div>
      </section>

      {/* ── Bench ────────────────────────────────────────────────────── */}
      {bench.length > 0 && (
        <section className="reveal" style={{ animationDelay: "160ms" }}>
          <div className="flex items-center justify-between mb-3">
            <SectionLabel>Bench — Next Best</SectionLabel>
            <span className="mono-label text-fg-mute">{bench.length} reserves</span>
          </div>
          <div className="well p-2">
            {bench.slice(0, 6).map((p, i) => (
              <div
                key={p.fantasy_key}
                className={`flex justify-between items-center px-4 py-2.5 ${i > 0 ? "border-t border-line-soft" : ""}`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="mono-value text-xs text-fg-mute">{String(i + 12).padStart(2, "0")}</span>
                  <span className="text-sm text-fg-dim truncate">{p.display_name}</span>
                  <span className="mono-label !text-[9px] text-fg-mute hidden sm:inline">{ROLE_LABELS[p.role]}</span>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  <span className="mono-value text-xs text-fg-mute hidden md:inline">{p.team}</span>
                  <span className="mono-value text-sm text-fg-dim w-14 text-right">{p.adjusted_score.toFixed(1)}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── AI Analyst Report ────────────────────────────────────────── */}
      <Panel className="p-6 reveal" >
        <div className="flex flex-wrap justify-between items-center gap-4 mb-5">
          <div className="flex items-center gap-3">
            <span className="text-accent">
              <IconTerminal size={18} />
            </span>
            <div>
              <SectionLabel accent>AI Analyst Report</SectionLabel>
              <p className="text-[11px] text-fg-mute mt-1">
                SHAP attributions + local llama3.2 narrative — fully offline
              </p>
            </div>
          </div>
          {!report && (
            <Button variant="outline" onClick={loadReport} disabled={reportLoading}>
              {reportLoading ? "Analyzing…" : "Generate Report"}
            </Button>
          )}
        </div>

        {reportError && (
          <div className="flex items-center gap-2.5 text-sm text-danger bg-danger/5 border border-danger/25 rounded-md p-3.5">
            <IconAlert size={15} className="shrink-0" />
            {reportError}
          </div>
        )}

        {reportLoading && (
          <div className="space-y-3">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-24 w-full" />
          </div>
        )}

        {report && (
          <div className="space-y-5">
            <div className="flex items-center gap-2">
              <Chip tone={report.generated_with === "ollama" ? "accent" : "neutral"}>
                {report.generated_with === "ollama" ? "Generated · llama3.2 local" : "Heuristic fallback"}
              </Chip>
              <Chip tone={report.attribution.covered_selected === report.attribution.selected_count ? "accent" : "neutral"}>
                {report.attribution.available ? `${report.attribution.method.replaceAll("_", " ")} drivers ${report.attribution.covered_selected}/${report.attribution.selected_count}` : "Feature attribution unavailable"}
              </Chip>
            </div>

            <p className="text-sm text-fg-dim leading-relaxed border-l-2 border-accent/70 pl-4">
              {report.team_report}
            </p>

            <div className="space-y-2.5">
              {report.players
                .filter((p) => p.selected)
                .map((p) => (
                  <div key={p.display_name} className="plate-flat p-4">
                    <div className="flex justify-between items-baseline mb-2 gap-4">
                      <span className="font-medium text-fg text-sm">{p.display_name}</span>
                      <span className="mono-value text-xs text-accent shrink-0">{p.adjusted_score.toFixed(1)} pts</span>
                    </div>
                    <p className="text-xs text-fg-dim leading-relaxed">{p.explanation}</p>
                    {p.drivers.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2.5">
                        {p.drivers.map((d) => (
                          <span
                            key={d.feature}
                            className={`mono-label !text-[9px] border rounded-[3px] px-1.5 py-0.5 mono-value ${
                              d.impact >= 0 ? "text-ok border-ok/35" : "text-danger border-danger/35"
                            }`}
                          >
                            {d.label}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
            </div>
          </div>
        )}
      </Panel>

      {/* ── Data coverage note ───────────────────────────────────────── */}
      {name_resolution.unresolved.length > 0 && (
        <div className="flex items-start gap-2.5 text-xs text-fg-mute plate-flat p-4 reveal">
          <IconAlert size={14} className="shrink-0 mt-px text-warn" />
          <p className="leading-relaxed">
            <span className="text-fg-dim font-medium">Data coverage:</span>{" "}
            {name_resolution.unresolved.length} squad player
            {name_resolution.unresolved.length > 1 ? "s" : ""} without {request.format.toUpperCase()} history
            {name_resolution.unresolved.length <= 8 ? ` (${name_resolution.unresolved.join(", ")})` : ""} — scored
            with the format league prior ({summary.league_prior.toFixed(1)} pts).
          </p>
        </div>
      )}
    </div>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="bg-panel px-4 py-3">
      <div className="flex items-center gap-1.5 text-fg-mute mb-1">
        {icon}
        <span className="mono-label !text-[9px]">{label}</span>
      </div>
      <div className="text-xs text-fg-dim truncate">{value}</div>
    </div>
  );
}

interface Props {
  result: GenerateResponse;
}

// Re-exported for pages that need a loading skeleton matching this view
export function AnalysisSkeleton({ label }: { label: string }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-2">
        <Progress />
        <span className="mono-label text-accent shrink-0">{label}</span>
      </div>
      <Panel className="p-6">
        <Skeleton className="h-3 w-28 mb-4" />
        <Skeleton className="h-6 w-72 mb-3" />
        <Skeleton className="h-3 w-96" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px mt-6 border border-line-soft rounded-md overflow-hidden">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-panel px-4 py-3.5">
              <Skeleton className="h-2.5 w-16 mb-2" />
              <Skeleton className="h-3 w-24" />
            </div>
          ))}
        </div>
      </Panel>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3.5">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-44 rounded-md" />
        ))}
      </div>
    </div>
  );
}
