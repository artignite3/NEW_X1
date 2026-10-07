"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { GenerateResponse, Match } from "@/lib/types";
import { generateBestTeam } from "@/lib/api";
import AnalysisResult, { AnalysisSkeleton } from "./AnalysisResult";
import { IconAlert, IconArrowRight, IconCalendar, IconPin } from "./icons";
import { Button, CheckRow, Chip, Rivets, SectionLabel, StatusDot } from "./ui";

interface Props {
  matches: Match[];
}

export default function FixturesBoard({ matches }: Props) {
  const [useMl, setUseMl] = useState(true);
  const [useIntelligence, setUseIntelligence] = useState(true);
  const [analyzing, setAnalyzing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GenerateResponse | null>(null);

  const { upcoming, todays, recentPast, feedStaleDays } = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const sorted = [...matches].sort((a, b) => a.date.localeCompare(b.date));
    const upcoming = sorted.filter((m) => new Date(m.date) >= today);
    const todays = sorted.filter((m) => new Date(m.date).getTime() === today.getTime());
    const recentPast = sorted
      .filter((m) => new Date(m.date) < today)
      .slice(-8)
      .reverse();
    const newest = sorted[sorted.length - 1];
    const feedStaleDays = newest
      ? Math.max(0, Math.floor((today.getTime() - new Date(newest.date).getTime()) / 86_400_000))
      : 0;
    return { upcoming, todays, recentPast, feedStaleDays };
  }, [matches]);

  const analyze = async (match: Match) => {
    setAnalyzing(String(match.match_id));
    setError(null);
    setResult(null);
    try {
      const res = await generateBestTeam({
        match_id: match.match_id,
        use_ml: useMl,
        use_intelligence: useIntelligence,
      });
      setResult(res);
      setTimeout(() => document.getElementById("analysis")?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Team generation failed");
    } finally {
      setAnalyzing(null);
    }
  };

  return (
    <div className="space-y-8">
      {/* ── Page header ──────────────────────────────────────────────── */}
      <div className="flex flex-wrap justify-between items-end gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-fg tracking-tight">Upcoming fixtures</h1>
          <p className="text-sm text-fg-mute mt-1.5">
            TriBE ensemble predictions, risk-adjusted XI optimization, live match intelligence.
          </p>
        </div>
        <Button onClick={() => (window.location.href = "/simulator")}>
          Custom Simulator
          <IconArrowRight size={13} />
        </Button>
      </div>

      {/* ── Engine controls ──────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2.5">
        <span className="mono-label text-fg-mute">Analysis engine</span>
        <CheckRow checked={useMl} onChange={setUseMl} label="TriBE ML" />
        <CheckRow checked={useIntelligence} onChange={setUseIntelligence} label="Match intelligence" />
      </div>

      {/* ── Banners ──────────────────────────────────────────────────── */}
      {todays.length > 0 && (
        <div className="flex items-center gap-2.5 text-sm text-fg-dim plate-flat px-4 py-3">
          <StatusDot tone="ok" pulse />
          <span>
            {todays.length} match{todays.length > 1 ? "es" : ""} today —{" "}
            {todays.map((m) => `${m.team1} v ${m.team2}`).join(", ")}
          </span>
        </div>
      )}

      {upcoming.length === 0 && feedStaleDays > 7 && (
        <div className="flex items-start gap-3 text-sm text-warn border border-warn/25 bg-warn/5 rounded-md px-4 py-3.5">
          <IconAlert size={15} className="shrink-0 mt-0.5" />
          <div>
            Fixture feed is {feedStaleDays} days old. Run{" "}
            <code className="mono-value text-[12px] text-warn">python data/future_matches/schedule_fetcher.py</code>{" "}
            to refresh — requires <span className="mono-value text-[12px]">RAPID_API_KEY</span> in{" "}
            <span className="mono-value text-[12px]">.env</span>. Recent fixtures below still support
            retrospective analysis.
          </div>
        </div>
      )}

      {/* ── Fixture list ─────────────────────────────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <SectionLabel>Fixture Schedule</SectionLabel>
          <span className="mono-label text-fg-mute">{upcoming.length} upcoming</span>
        </div>

        <div className="well p-2.5">
          {upcoming.map((match, i) => (
            <FixtureRow
              key={match.match_id}
              match={match}
              index={i}
              analyzing={analyzing === String(match.match_id)}
              disabled={analyzing !== null}
              onAnalyze={() => analyze(match)}
            />
          ))}

          {upcoming.length === 0 && recentPast.length > 0 && (
            <div className="px-4 py-3">
              <span className="mono-label text-fg-mute">
                No upcoming fixtures — recent completed matches below
              </span>
            </div>
          )}

          {upcoming.length === 0 &&
            recentPast.map((match, i) => (
              <FixtureRow
                key={match.match_id}
                match={match}
                index={i}
                dim
                analyzing={analyzing === String(match.match_id)}
                disabled={analyzing !== null}
                onAnalyze={() => analyze(match)}
              />
            ))}

          {upcoming.length === 0 && recentPast.length === 0 && (
            <div className="px-6 py-14 text-center">
              <div className="mono-label text-fg-mute mb-2">No fixtures in local feed</div>
              <p className="text-xs text-fg-mute/70">
                Run the data sync pipeline to populate the schedule.
              </p>
            </div>
          )}
        </div>
      </section>

      {/* ── Analysis ─────────────────────────────────────────────────── */}
      <div id="analysis" className="scroll-mt-20">
        {error && (
          <div className="flex items-start gap-2.5 text-sm text-danger bg-danger/5 border border-danger/25 rounded-md p-4">
            <IconAlert size={15} className="shrink-0 mt-0.5" />
            {error}
          </div>
        )}
        {analyzing && <AnalysisSkeleton label="Running TriBE ensemble + optimizer" />}
        {result && !analyzing && <AnalysisResult result={result} />}
      </div>
    </div>
  );
}

// ── Fixture row: status dot | teams | venue field | date | action ───────────

function FixtureRow({
  match,
  index,
  dim = false,
  analyzing,
  disabled,
  onAnalyze,
}: {
  match: Match;
  index: number;
  dim?: boolean;
  analyzing: boolean;
  disabled: boolean;
  onAnalyze: () => void;
}) {
  const hasSquad = match.has_squad !== false;
  return (
    <div
      className={`reveal ${index > 0 ? "mt-2" : ""}`}
      style={{ animationDelay: `${index * 55}ms` }}
    >
      <div
        className={`plate px-4 py-3.5 flex flex-wrap items-center gap-x-5 gap-y-3 transition-colors duration-150 hover:border-fg-mute/50 ${
          dim ? "opacity-70" : ""
        }`}
      >
        <Rivets />

        <div className="flex items-center gap-2.5 w-32 shrink-0">
          <StatusDot tone={hasSquad ? "ok" : "mute"} pulse={hasSquad} />
          <span className="mono-label !text-[9px] text-fg-mute leading-tight">
            {hasSquad ? "Squads ready" : "Squads pending"}
          </span>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`font-semibold text-[15px] ${dim ? "text-fg-dim" : "text-fg"}`}>
              {match.team1}
              <span className="text-fg-mute font-normal mx-1.5">vs</span>
              {match.team2}
            </span>
            <Chip>{match.match_type}</Chip>
          </div>
          <div className="field mt-2 px-2.5 py-1.5 inline-flex items-center gap-2 max-w-full">
            <span className="text-fg-mute shrink-0">
              <IconPin size={12} />
            </span>
            <span className="mono-value text-[11px] text-fg-dim truncate">{match.venue}</span>
          </div>
        </div>

        <div className="flex items-center gap-1.5 text-fg-mute shrink-0">
          <IconCalendar size={13} />
          <span className="mono-value text-xs">{match.date}</span>
        </div>

        <Button
          variant="outline"
          onClick={onAnalyze}
          disabled={disabled}
          className="shrink-0 !px-3.5 !py-2"
        >
          {analyzing ? "Analyzing" : dim ? "Retrospective" : "Analyze"}
        </Button>
      </div>
    </div>
  );
}
