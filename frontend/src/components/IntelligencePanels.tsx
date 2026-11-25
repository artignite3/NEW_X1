"use client";

import type { PitchProfile, PitchWindow, Weather } from "@/lib/types";
import { IconDroplet, IconWind } from "./icons";

const sentence = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase().replaceAll("_", " ") : s);
const signed = (n: number | null | undefined) => (n === null || n === undefined ? "n/a" : `${n >= 0 ? "+" : "−"}${Math.abs(n)}%`);

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-fg-mute">{label}</div>
      <div className="mono-value text-sm text-fg mt-1">{value}</div>
    </div>
  );
}

export function WeatherPanel({ weather }: { weather: Weather }) {
  if (weather.available === false) {
    return (
      <div className="plate p-6">
        <h3 className="text-sm font-medium text-fg">Match weather</h3>
        <p className="text-sm text-fg-dim mt-2">{weather.summary}</p>
      </div>
    );
  }
  const flags = [weather.seam_swing_advantage && "Helps swing bowling", weather.dew_risk && "Dew likely later in the match"].filter(Boolean);
  return (
    <div className="plate p-6">
      <h3 className="text-sm font-medium text-fg">Match weather</h3>
      <div className="flex items-end justify-between gap-6 mt-4 pb-4 border-b border-line-soft">
        <div className="mono-value text-[32px] leading-none font-medium text-fg">{Math.round(weather.temperature_c)}°C</div>
        <div className="grid grid-cols-3 gap-6 text-right">
          <Stat label="Humidity" value={`${weather.humidity_pct}%`} />
          <Stat label="Cloud" value={`${weather.cloud_cover_pct}%`} />
          <Stat label="Wind" value={`${weather.wind_speed_kmh.toFixed(0)} km/h`} />
        </div>
      </div>
      <p className="text-sm text-fg-dim mt-4 leading-relaxed break-words">{weather.summary}</p>
      {flags.length > 0 && <ul className="text-sm text-fg mt-2 space-y-1">{flags.map((f) => <li key={String(f)}>{f}</li>)}</ul>}
    </div>
  );
}

function HistoryWindow({ title, window }: { title: string; window: PitchWindow }) {
  return (
    <div className="rounded-lg border border-line-soft p-4 min-w-0">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm text-fg">{title}</span>
        <span className="mono-value text-xs text-fg-mute">{window.matches} matches</span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-3">
        <Stat label="Runs per over" value={window.runs_per_over?.toFixed(2) ?? "n/a"} />
        <Stat label="Boundaries" value={window.boundary_pct === null ? "n/a" : `${window.boundary_pct}%`} />
        <Stat label="1st innings*" value={window.avg_1st_innings?.toFixed(0) ?? "n/a"} />
        <Stat label="Wickets*" value={window.wickets_per_innings?.toFixed(1) ?? "n/a"} />
      </div>
      <p className="text-xs text-fg-mute mt-3 leading-relaxed">
        <span className="mono-value">{window.from_date}</span> to <span className="mono-value">{window.to_date}</span>.
        Starred figures use {window.same_format_matches} same-format matches. Defended {window.defended} of{" "}
        {window.decided_limited_overs} decided limited-overs games, {window.low_total_defences} with below-peer totals.
      </p>
    </div>
  );
}

export function PitchPanel({ pitch }: { pitch: PitchProfile }) {
  const source =
    pitch.source === "historical" ? `Venue history, ${pitch.confidence} confidence`
    : pitch.source === "curated_prior" ? `Curated profile for ${pitch.format.toUpperCase()}`
    : "No profile, neutral multipliers";
  return (
    <div className="plate p-6">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-medium text-fg">Pitch</h3>
        <span className="text-xs text-fg-mute">{source}</span>
      </div>

      <div className="flex items-end justify-between gap-6 mt-4 pb-4 border-b border-line-soft">
        <div className="text-[22px] leading-tight font-medium text-fg">{sentence(pitch.category)}</div>
        <div className="grid grid-cols-3 gap-6 text-right shrink-0">
          <Stat label="Batters" value={`×${pitch.batter_mult.toFixed(2)}`} />
          <Stat label="Pace" value={`×${pitch.pacer_mult.toFixed(2)}`} />
          <Stat label="Spin" value={`×${pitch.spinner_mult.toFixed(2)}`} />
        </div>
      </div>

      <p className="text-sm text-fg-dim mt-4 leading-relaxed break-words">{pitch.description}</p>

      {pitch.source === "historical" && (
        <div className="mt-4 space-y-4">
          <dl className="grid grid-cols-3 gap-4">
            <Stat label="Bowling bias" value={sentence(pitch.bowling_bias ?? "Insufficient evidence")} />
            <Stat label="Scoring vs peers" value={signed(pitch.scoring_vs_peers_pct)} />
            <Stat label="Wickets vs peers" value={signed(pitch.wickets_vs_peers_pct)} />
          </dl>
          {pitch.style_evidence && (
            <p className="text-xs text-fg-mute leading-relaxed">
              Based on {pitch.style_evidence.pace.balls} pace and {pitch.style_evidence.spin.balls} spin legal balls at this venue
            </p>
          )}
          <div className="grid gap-3">
            {pitch.last5 && <HistoryWindow title="Last 5" window={pitch.last5} />}
            {pitch.last10 && <HistoryWindow title="Last 10" window={pitch.last10} />}
          </div>
          <div className="text-xs text-fg-mute leading-relaxed space-y-1">
            <p>
              As of <span className="mono-value">{pitch.as_of}</span>, derived from{" "}
              <a className="underline underline-offset-2" href="https://cricsheet.org/" target="_blank" rel="noreferrer">Cricsheet data</a>{" "}
              (<a className="underline underline-offset-2" href="https://cricsheet.org/licensing/" target="_blank" rel="noreferrer">ODC Attribution licence</a>).
            </p>
            <p>Team adjustments stay neutral.{pitch.snapshot_fallback ? " The last validated backup is in use." : ""}</p>
          </div>
        </div>
      )}
    </div>
  );
}

export function WeatherInline({ weather }: { weather: Weather }) {
  if (weather.available === false) return <span className="text-fg-mute">Weather unavailable</span>;
  return (
    <span className="inline-flex items-center gap-1 text-fg-mute">
      <IconWind size={14} />
      <span className="mono-value">{Math.round(weather.temperature_c)}°C</span>
      <IconDroplet size={14} />
      <span className="mono-value">{weather.humidity_pct}%</span>
    </span>
  );
}
