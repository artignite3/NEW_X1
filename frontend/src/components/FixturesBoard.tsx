"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { GenerateResponse, Match } from "@/lib/types";
import { generateBestTeam } from "@/lib/api";
import AnalysisResult, { AnalysisSkeleton } from "./AnalysisResult";
import OvalGraphic from "./OvalGraphic";
import { IconPin } from "./icons";
import { Button, CheckRow, Notice, PageHeader, Skeleton, StatusDot } from "./ui";

interface Props {
  matches: Match[];
  feedWarning?: string | null;
  offline?: boolean;
  loading?: boolean;
}

const DAY = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", timeZone: "UTC" });
const WEEKDAY = new Intl.DateTimeFormat("en-GB", { weekday: "short", timeZone: "UTC" });

export default function FixturesBoard({ matches, feedWarning, offline = false, loading = false }: Props) {
  const [scanNews, setScanNews] = useState(false);
  const [useMl, setUseMl] = useState(true);
  const [useIntelligence, setUseIntelligence] = useState(true);
  const [analyzing, setAnalyzing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GenerateResponse | null>(null);

  const { upcoming, todays, recentPast, feedStaleDays } = useMemo(() => {
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    const sorted = [...matches].sort((a, b) => a.date.localeCompare(b.date));
    const upcoming = sorted.filter((m) => m.date > today);
    const todays = sorted.filter((m) => m.date === today);
    const recentPast = sorted.filter((m) => m.date < today && m.date > "2025-06-30").slice(-8).reverse();
    const newest = sorted[sorted.length - 1];
    const feedStaleDays = newest ? Math.max(0, Math.floor((Date.parse(today) - Date.parse(newest.date)) / 86_400_000)) : 0;
    return { upcoming, todays, recentPast, feedStaleDays };
  }, [matches]);

  const analyze = async (match: Match) => {
    setAnalyzing(String(match.match_id));
    setError(null);
    setResult(null);
    try {
      const res = await generateBestTeam({
        match_id: match.match_id,
        mode: recentPast.some((m) => m.match_id === match.match_id) ? "retrospective" : "prediction",
        scan_news: scanNews,
        use_ml: useMl,
        use_intelligence: useIntelligence,
      });
      setResult(res);
      setTimeout(() => document.getElementById("analysis")?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Team selection could not be generated");
    } finally {
      setAnalyzing(null);
    }
  };

  const showRecent = upcoming.length === 0 && recentPast.length > 0;
  const rows = upcoming.length > 0 ? upcoming : recentPast;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Upcoming fixtures"
        subtitle="Pick a match to see the projected best XI, the captain and the reasons behind each selection"
        action={
          <Link
            href="/simulator"
            className="inline-flex items-center justify-center gap-2 h-9 px-4 rounded-lg border border-line text-sm font-medium text-fg hover:bg-panel-hi transition-colors shrink-0"
          >
            Custom match
          </Link>
        }
      />

      {feedWarning && <Notice>{feedWarning}</Notice>}

      {upcoming.length === 0 && feedStaleDays > 7 && matches.length > 0 && (
        <Notice>
          The fixture feed is {feedStaleDays} days old. Recent completed matches below can still be analysed
          retrospectively
        </Notice>
      )}

      {todays.length > 0 && (
        <p className="flex items-center gap-2 text-sm text-fg-dim">
          <StatusDot tone="ok" />
          Today: {todays.map((m) => `${m.team1} v ${m.team2}`).join(", ")}
        </p>
      )}

      <section className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div className="flex items-baseline gap-3">
            <h2 className="text-sm font-medium text-fg">{showRecent ? "Recent matches" : "Schedule"}</h2>
            {rows.length > 0 && <span className="mono-value text-xs text-fg-mute">
              {showRecent ? `${recentPast.length} completed` : `${upcoming.length} upcoming`}
            </span>}
          </div>
          {(rows.length > 0 || loading) && <div className="flex flex-wrap items-center gap-x-5" aria-label="Analysis options">
            <CheckRow checked={useMl} onChange={setUseMl} label="Model predictions" />
            <CheckRow checked={useIntelligence} onChange={setUseIntelligence} label="Weather and pitch" />
            <CheckRow checked={scanNews} onChange={setScanNews} label="Injury news" />
          </div>}
        </div>

        {loading ? (
          <div className="plate divide-y divide-line-soft overflow-hidden" aria-busy aria-label="Loading fixtures">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="grid grid-cols-[56px_1fr] md:grid-cols-[72px_1fr_176px_auto] items-center gap-x-4 px-4 py-4">
                <Skeleton className="h-8 w-12" />
                <div className="space-y-2">
                  <Skeleton className="h-4 w-56 max-w-full" />
                  <Skeleton className="h-3 w-40 max-w-full" />
                </div>
                <Skeleton className="hidden md:block h-4 w-32" />
                <Skeleton className="hidden md:block h-9 w-24" />
              </div>
            ))}
          </div>
        ) : rows.length > 0 ? (
          <div className="plate divide-y divide-line-soft overflow-hidden">
            {rows.map((match) => (
              <FixtureRow
                key={match.match_id}
                match={match}
                past={showRecent}
                analyzing={analyzing === String(match.match_id)}
                disabled={analyzing !== null}
                onAnalyze={() => analyze(match)}
              />
            ))}
          </div>
        ) : (
          <div className="plate px-6 py-12 flex flex-col items-center text-center">
            <OvalGraphic />
            <h3 className="text-base font-medium text-fg mt-6">
              {offline ? "Fixtures are offline" : "No fixtures in the next seven days"}
            </h3>
            <p className="text-sm text-fg-dim mt-2 max-w-md">
              {offline
                ? "The schedule loads from the analysis server, which is not running right now. You can still set up a match in the simulator"
                : "New fixtures appear once squads are announced. You can set up any match in the simulator"}
            </p>
            <Link href="/simulator" className="mt-6 inline-flex items-center gap-2 h-9 px-4 rounded-lg bg-fg text-accent-ink text-sm font-medium hover:bg-white transition-colors">
              Open simulator
            </Link>
          </div>
        )}
      </section>

      <div id="analysis" className="scroll-mt-24 space-y-6">
        {error && <Notice tone="danger">{error}</Notice>}
        {analyzing && <AnalysisSkeleton label="Predicting players and solving for the best XI" />}
        {result && !analyzing && <AnalysisResult result={result} />}
      </div>
    </div>
  );
}

function FixtureRow({
  match,
  past,
  analyzing,
  disabled,
  onAnalyze,
}: {
  match: Match;
  past: boolean;
  analyzing: boolean;
  disabled: boolean;
  onAnalyze: () => void;
}) {
  const hasSquad = match.has_squad !== false;
  const projected = match.squad_source === "last_match";
  const reused = match.squad_source === "series_squad";
  const squadLabel = projected ? "Last-match XIs" : reused ? "Series squads" : hasSquad ? "Squads announced" : "Squads pending";
  const squadTitle = reused
    ? "Provider series roster; playing XI unconfirmed"
    : match.squad_match_dates
      ? Object.entries(match.squad_match_dates).map(([team, day]) => `${team}: ${day}`).join(", ")
      : undefined;
  const when = new Date(`${match.date}T00:00:00Z`);
  const valid = !Number.isNaN(when.getTime());

  return (
    <div className={`grid grid-cols-[56px_1fr] md:grid-cols-[72px_1fr_176px_auto] items-center gap-x-4 gap-y-3 px-4 py-4 ${past ? "text-fg-dim" : ""}`}>
      <div className="mono-value leading-tight">
        <div className="text-sm text-fg">{valid ? DAY.format(when) : match.date}</div>
        <div className="text-xs text-fg-mute mt-1">{valid ? WEEKDAY.format(when) : ""}</div>
      </div>

      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[15px] font-medium text-fg break-words">
            {match.team1}
            <span className="text-fg-mute font-normal mx-2">v</span>
            {match.team2}
          </span>
          <span className="mono-value text-xs text-fg-mute">{match.match_type}</span>
        </div>
        <div className="flex items-center gap-1 mt-1 text-sm text-fg-mute min-w-0">
          <IconPin size={14} className="shrink-0" />
          <span className="truncate">{match.venue}</span>
        </div>
      </div>

      <div className="col-start-2 md:col-start-auto flex items-center gap-2 text-sm text-fg-dim" title={squadTitle}>
        <StatusDot tone={projected || reused ? "warn" : hasSquad ? "ok" : "mute"} />
        {squadLabel}
      </div>

      <div className="col-start-2 md:col-start-auto">
        <Button variant="outline" onClick={onAnalyze} disabled={disabled || !hasSquad} className="w-full md:w-auto">
          {analyzing ? "Analysing" : past ? "Review" : "Analyse"}
        </Button>
      </div>
    </div>
  );
}
