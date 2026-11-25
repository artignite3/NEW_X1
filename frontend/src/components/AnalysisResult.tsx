"use client";

import { useEffect, useRef, useState } from "react";
import type { AnalystReport, GenerateResponse, PlayerEntry } from "@/lib/types";
import { explainTeam, saveAnalysis } from "@/lib/api";
import { PitchPanel, WeatherPanel } from "./IntelligencePanels";
import { ENGINE_LABELS, ROLE_LABELS, ROLE_SHORT } from "./RoleBadge";
import { IconCalendar, IconPin } from "./icons";
import { Button, Notice, Panel, Skeleton } from "./ui";

// Tween for the team total: a changed number counts to its new value
function useCountUp(target: number, duration = 600): number {
  const [value, setValue] = useState(target);
  const prev = useRef(target);
  useEffect(() => {
    const reduced = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
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
      setValue(from + (target - from) * (1 - Math.pow(1 - t, 3)));
      if (t < 1) raf = requestAnimationFrame(tick);
      else prev.current = target;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return value;
}

const pad = (n: number) => String(n).padStart(2, "0");

export default function AnalysisResult({ result }: Props) {
  const [report, setReport] = useState<AnalystReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const [saveError, setSaveError] = useState("");

  const { request, best_team, bench, summary, intelligence, name_resolution } = result;
  const total = useCountUp(summary.expected_total_points);
  const engineLabel = summary.engine.replace(/\s*\(.*\)$/, "");
  const format = request.format.toUpperCase() === "TEST" ? "Test" : request.format.toUpperCase();
  const usingBackup = Object.values(result.data_provenance).some((value) => value === "last_good");

  const loadReport = async () => {
    setReportLoading(true);
    setReportError(null);
    try {
      setReport(await explainTeam(result.explain_token));
    } catch (e) {
      setReportError(e instanceof Error ? e.message : "The report could not be generated");
    } finally {
      setReportLoading(false);
    }
  };

  const save = async () => {
    setSaveState("saving");
    setSaveError("");
    try {
      await saveAnalysis(result.explain_token, `${request.team1} vs ${request.team2}, ${request.date}`.slice(0, 120));
      setSaveState("saved");
    } catch (error) {
      setSaveState("idle");
      setSaveError(error instanceof Error ? error.message : "Could not save. Try again");
    }
  };

  const facts: [string, string][] = [
    ["Format", format],
    ["Model", engineLabel],
    ["Team split", Object.entries(summary.team_split).map(([t, n]) => `${n} ${t}`).join(", ")],
    ["Role mix", (["WK", "BAT", "AR", "BOWL"] as const).filter((r) => summary.role_counts[r] > 0).map((r) => `${summary.role_counts[r]} ${ROLE_SHORT[r]}`).join(", ")],
    ["Constraints", `${summary.constraint_mode.replaceAll("_", " ")}, ${result.validation.valid ? "verified" : "not met"}`],
    ["Solver", `${summary.solver_status}, squad of ${summary.squad_size}`],
    ["Names matched", `${name_resolution.resolved} of ${summary.squad_size}`],
  ];

  return (
    <div className="space-y-6 reveal">
      {/* ── Match header ─────────────────────────────────────────────── */}
      <Panel className="p-6">
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-6">
          <div className="min-w-0">
            <h2 className="text-2xl font-medium text-fg break-words">
              {request.team1}
              <span className="text-fg-mute font-normal mx-2">v</span>
              {request.team2}
            </h2>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm text-fg-mute">
              <span className="inline-flex items-center gap-1 min-w-0">
                <IconPin size={14} className="shrink-0" />
                <span className="truncate">{request.venue}</span>
              </span>
              <span className="inline-flex items-center gap-1">
                <IconCalendar size={14} />
                <span className="mono-value">{request.date}</span>
              </span>
            </div>
          </div>

          <div className="md:text-right shrink-0">
            <div className="mono-value text-[40px] leading-none font-medium text-accent">{total.toFixed(0)}</div>
            <div className="text-sm text-fg-mute mt-2">Projected team points</div>
            <dl className="text-sm mt-2 space-y-1">
              <div><dt className="inline text-fg-mute">Captain </dt><dd className="inline text-fg">{summary.captain}</dd></div>
              <div><dt className="inline text-fg-mute">Vice-captain </dt><dd className="inline text-fg-dim">{summary.vice_captain}</dd></div>
            </dl>
          </div>
        </div>

        <dl className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-x-6 gap-y-4 mt-6 pt-6 border-t border-line-soft">
          {facts.map(([label, value]) => (
            <div key={label} className="min-w-0">
              <dt className="text-xs text-fg-mute">{label}</dt>
              <dd className="text-sm text-fg-dim mt-1 truncate" title={value}>{value}</dd>
            </div>
          ))}
        </dl>

        <div className="flex flex-wrap items-center gap-3 mt-6">
          <Button variant="outline" disabled={saveState !== "idle"} onClick={save}>
            {saveState === "saving" ? "Saving" : saveState === "saved" ? "Saved to your account" : "Save analysis"}
          </Button>
          {saveError && <span className="text-sm text-danger" role="status">{saveError}</span>}
        </div>
      </Panel>

      {(result.data_provenance.warnings.length > 0 || usingBackup) && (
        <Notice>
          {usingBackup ? "Using verified backup data. " : ""}
          {result.data_provenance.warnings.join(" ")}
        </Notice>
      )}

      {/* ── Scorecard ────────────────────────────────────────────────── */}
      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h3 className="text-sm font-medium text-fg">Selected XI</h3>
          <span className="text-xs text-fg-mute">Points are projected fantasy points with an estimated range</span>
        </div>
        <div className="plate overflow-hidden">
          <ScorecardHead />
          <div className="divide-y divide-line-soft">
            {best_team.map((p, i) => (
              <ScorecardRow
                key={p.fantasy_key}
                player={p}
                number={i + 1}
                mark={p.display_name === summary.captain ? "C" : p.display_name === summary.vice_captain ? "VC" : undefined}
              />
            ))}
          </div>
          <div className="flex items-center justify-between px-4 py-3 border-t border-line bg-well">
            <span className="text-sm text-fg-dim">Projected total</span>
            <span className="mono-value text-base font-medium text-accent">{summary.expected_total_points.toFixed(1)}</span>
          </div>
        </div>
      </section>

      {bench.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-baseline justify-between">
            <h3 className="text-sm font-medium text-fg">Bench</h3>
            <span className="mono-value text-xs text-fg-mute">next {Math.min(bench.length, 6)} of {bench.length}</span>
          </div>
          <div className="plate overflow-hidden divide-y divide-line-soft">
            {bench.slice(0, 6).map((p, i) => (
              <ScorecardRow key={p.fantasy_key} player={p} number={i + 12} muted />
            ))}
          </div>
        </section>
      )}

      {/* ── Conditions ───────────────────────────────────────────────── */}
      {intelligence.enabled && (intelligence.weather || intelligence.pitch) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
          {intelligence.weather && <WeatherPanel weather={intelligence.weather} />}
          {intelligence.pitch && <PitchPanel pitch={intelligence.pitch} />}
        </div>
      )}

      {/* ── Analyst report ───────────────────────────────────────────── */}
      <Panel className="p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h3 className="text-sm font-medium text-fg">Why these players</h3>
            <p className="text-sm text-fg-mute mt-1">The main drivers behind each selection, with a written summary</p>
          </div>
          {!report && (
            <Button variant="outline" onClick={loadReport} disabled={reportLoading} className="w-full sm:w-auto">
              {reportLoading ? "Writing report" : "Explain selection"}
            </Button>
          )}
        </div>

        {reportError && <div className="mt-4"><Notice tone="danger">{reportError}</Notice></div>}

        {reportLoading && (
          <div className="space-y-3 mt-6">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-24 w-full" />
          </div>
        )}

        {report && (
          <div className="mt-6 space-y-6">
            <p className="text-xs text-fg-mute">
              {report.generated_with === "ollama" ? "Written by a local language model." : "Rule-based summary."}{" "}
              {report.attribution.available
                ? `${report.attribution.method.replaceAll("_", " ")} drivers for ${report.attribution.covered_selected} of ${report.attribution.selected_count} players.`
                : "Feature drivers unavailable."}
            </p>
            <p className="text-[15px] leading-relaxed text-fg max-w-3xl break-words">{report.team_report}</p>

            <div className="divide-y divide-line-soft border-t border-line-soft">
              {report.players.filter((p) => p.selected).map((p) => (
                <div key={p.display_name} className="py-4 grid gap-2 md:grid-cols-[200px_1fr] md:gap-6">
                  <div className="flex md:flex-col justify-between md:justify-start gap-1">
                    <span className="text-sm font-medium text-fg truncate">{p.display_name}</span>
                    <span className="mono-value text-sm text-fg-dim">{p.adjusted_score.toFixed(1)}</span>
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm text-fg-dim leading-relaxed break-words">{p.explanation}</p>
                    {p.drivers.length > 0 && (
                      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs">
                        {p.drivers.map((d) => (
                          <span key={d.feature} className={d.impact >= 0 ? "text-ok" : "text-danger"}>
                            {d.impact >= 0 ? "+" : "−"} {d.label}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Panel>

      {name_resolution.unresolved.length > 0 && (
        <p className="text-sm text-fg-mute leading-relaxed">
          {name_resolution.unresolved.length} squad player{name_resolution.unresolved.length > 1 ? "s have" : " has"} no {format} history
          {name_resolution.unresolved.length <= 8 ? ` (${name_resolution.unresolved.join(", ")})` : ""} and{" "}
          {name_resolution.unresolved.length > 1 ? "are" : "is"} scored at the format average of{" "}
          <span className="mono-value">{summary.league_prior.toFixed(1)}</span> points.
        </p>
      )}
    </div>
  );
}

const ROW_GRID = "grid grid-cols-[32px_1fr_auto] md:grid-cols-[40px_1fr_96px_160px_96px_72px] items-center gap-x-4";

function ScorecardHead() {
  return (
    <div className={`${ROW_GRID} hidden md:grid px-4 h-10 border-b border-line text-xs text-fg-mute`}>
      <span>No</span>
      <span>Player</span>
      <span>Role</span>
      <span>Team</span>
      <span className="text-right">Range</span>
      <span className="text-right">Points</span>
    </div>
  );
}

function ScorecardRow({ player, number, mark, muted = false }: { player: PlayerEntry; number: number; mark?: "C" | "VC"; muted?: boolean }) {
  const out = ["INJURED", "RESTED", "SUSPENDED"].includes(player.injury_status);
  const doubtful = player.injury_status === "DOUBTFUL";
  const notes: { text: string; tone?: "warn" | "danger" }[] = [];
  if (player.engine !== "ml") notes.push({ text: ENGINE_LABELS[player.engine] ?? ENGINE_LABELS.league_prior });
  if (player.pitch_multiplier !== 1) notes.push({ text: `Pitch ×${player.pitch_multiplier.toFixed(2)}` });
  if (doubtful) notes.push({ text: "Doubtful, XI unconfirmed", tone: "warn" });
  if (out) notes.push({ text: player.injury_status.charAt(0) + player.injury_status.slice(1).toLowerCase(), tone: "danger" });
  if (player.matches_played === 0) notes.push({ text: "No history" });
  else notes.push({ text: `${player.matches_played} matches` }, { text: `Ceiling ${player.captain_upside.toFixed(0)}` });

  return (
    <div className={`${ROW_GRID} px-4 py-3 ${out ? "opacity-60" : ""}`}>
      <span className={`mono-value text-sm ${muted ? "text-fg-mute" : "text-fg-dim"}`}>{pad(number)}</span>

      <div className="min-w-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`text-sm font-medium truncate ${muted ? "text-fg-dim" : "text-fg"}`}>{player.display_name}</span>
          {mark && (
            <span
              className={`mono-value text-[11px] leading-none px-1 py-0.5 rounded ${mark === "C" ? "bg-accent text-accent-ink" : "border border-line text-fg-dim"}`}
              title={mark === "C" ? "Captain" : "Vice-captain"}
            >
              {mark}
            </span>
          )}
        </div>
        <ul className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-fg-mute mt-1">
          <li className="md:hidden">{ROLE_LABELS[player.role]}</li>
          <li className="md:hidden">{player.team}</li>
          {notes.map((n) => (
            <li key={n.text} className={n.tone === "warn" ? "text-warn" : n.tone === "danger" ? "text-danger" : ""}>
              {n.text}
            </li>
          ))}
        </ul>
      </div>

      <span className="hidden md:block text-sm text-fg-dim">{ROLE_LABELS[player.role]}</span>
      <span className="hidden md:block text-sm text-fg-dim truncate">{player.team}</span>
      <span className="hidden md:block mono-value text-sm text-fg-mute text-right" title="Historical spread estimate; coverage is not calibrated">
        {player.ci_low.toFixed(0)} to {player.ci_high.toFixed(0)}
      </span>
      <span className={`mono-value text-sm text-right ${muted ? "text-fg-dim" : "text-fg"}`}>{player.adjusted_score.toFixed(1)}</span>
    </div>
  );
}

interface Props {
  result: GenerateResponse;
}

export function AnalysisSkeleton({ label }: { label: string }) {
  return (
    <div className="space-y-6" aria-busy>
      <p className="text-sm text-fg-dim" role="status">{label}</p>
      <Panel className="p-6">
        <Skeleton className="h-4 w-32 max-w-full" />
        <Skeleton className="h-7 w-72 max-w-full mt-3" />
        <Skeleton className="h-4 w-96 max-w-full mt-3" />
      </Panel>
      <div className="plate divide-y divide-line-soft overflow-hidden">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="px-4 py-4 flex items-center gap-4">
            <Skeleton className="h-4 w-6" />
            <Skeleton className="h-4 w-48 max-w-full" />
            <Skeleton className="h-4 w-12 ml-auto" />
          </div>
        ))}
      </div>
    </div>
  );
}
