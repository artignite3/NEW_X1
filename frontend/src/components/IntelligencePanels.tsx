"use client";

import type { PitchProfile, PitchWindow, Weather } from "@/lib/types";
import { IconCloud, IconDroplet, IconLayers, IconWind } from "./icons";
import { Chip, Rivets, SectionLabel } from "./ui";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="mono-value text-sm text-fg">{value}</div>
      <div className="mono-label !text-[9px] text-fg-mute mt-1">{label}</div>
    </div>
  );
}

export function WeatherPanel({ weather }: { weather: Weather }) {
  if (weather.available === false) return <div className="plate p-5"><SectionLabel>Match weather</SectionLabel><p className="text-xs text-fg-dim mt-3">{weather.summary}</p></div>;
  return (
    <div className="plate p-5">
      <Rivets />
      <div className="flex items-center justify-between mb-4">
        <SectionLabel accent>Match Weather</SectionLabel>
        <span className="text-fg-mute">
          <IconCloud size={16} />
        </span>
      </div>

      <div className="flex items-end justify-between border-y border-line-soft py-3">
        <div>
          <div className="mono-value text-[26px] leading-none font-medium text-fg">
            {Math.round(weather.temperature_c)}°C
          </div>
          <div className="mono-label text-fg-mute mt-1.5">Temperature</div>
        </div>
        <div className="grid grid-cols-3 gap-4 text-right">
          <Stat label="Humidity" value={`${weather.humidity_pct}%`} />
          <Stat label="Cloud" value={`${weather.cloud_cover_pct}%`} />
          <Stat label="Wind" value={`${weather.wind_speed_kmh.toFixed(0)}km/h`} />
        </div>
      </div>

      <p className="text-xs text-fg-dim mt-3 leading-relaxed">{weather.summary}</p>

      {(weather.seam_swing_advantage || weather.dew_risk) && (
        <div className="flex gap-1.5 mt-3">
          {weather.seam_swing_advantage && <Chip tone="ok">Swing-friendly</Chip>}
          {weather.dew_risk && <Chip tone="accent">Dew risk</Chip>}
        </div>
      )}
    </div>
  );
}

const PITCH_TONES: Record<string, string> = {
  BATTING: "text-ok border-ok/40",
  BOWLING: "text-danger border-danger/40",
  "SPIN FRIENDLY": "text-warn border-warn/40",
  NEUTRAL: "text-fg-dim border-line",
};

function HistoryWindow({ title, window }: { title: string; window: PitchWindow }) {
  return (
    <div className="border border-line-soft rounded-[4px] p-3">
      <div className="mono-label text-fg mb-2">{title} · {window.matches} matches</div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Runs / over" value={window.runs_per_over?.toFixed(2) ?? "—"} />
        <Stat label="Boundaries" value={window.boundary_pct === null ? "—" : `${window.boundary_pct}%`} />
        <Stat label="1st innings*" value={window.avg_1st_innings?.toFixed(0) ?? "—"} />
        <Stat label="Wickets*" value={window.wickets_per_innings?.toFixed(1) ?? "—"} />
      </div>
      <div className="mono-label text-fg-mute mt-2">{window.from_date} to {window.to_date} · *{window.same_format_matches} same-format matches</div>
      <div className="mono-label text-fg-mute mt-1">Defended {window.defended}/{window.decided_limited_overs} decided limited-over games · {window.low_total_defences} below-peer totals defended</div>
    </div>
  );
}

export function PitchPanel({ pitch }: { pitch: PitchProfile }) {
  return (
    <div className="plate p-5">
      <Rivets />
      <div className="flex items-center justify-between mb-4">
        <SectionLabel accent>Pitch Profile</SectionLabel>
        <span className="text-fg-mute">
          <IconLayers size={16} />
        </span>
      </div>

      <div className="flex items-end justify-between border-y border-line-soft py-3">
        <div>
          <span className={`mono-label border rounded-[4px] px-2 py-1 ${PITCH_TONES[pitch.category] ?? PITCH_TONES.NEUTRAL}`}>
            {pitch.category}
          </span>
          <div className="mono-label text-fg-mute mt-2">
            {pitch.source === "historical" ? `Historical venue trend · ${pitch.confidence} confidence` :
              pitch.source === "curated_prior" ? `Curated prior · ${pitch.format.toUpperCase()}` : "Profile unavailable · neutral"}
          </div>
        </div>
        <div className="grid grid-cols-3 gap-4 text-right">
          <Stat label="Batters" value={`×${pitch.batter_mult.toFixed(2)}`} />
          <Stat label="Pacers" value={`×${pitch.pacer_mult.toFixed(2)}`} />
          <Stat label="Spin" value={`×${pitch.spinner_mult.toFixed(2)}`} />
        </div>
      </div>

      <p className="text-xs text-fg-dim mt-3 leading-relaxed">{pitch.description}</p>
      {pitch.source === "historical" && (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap gap-2">
            <Chip tone="accent">{pitch.bowling_bias ?? "INSUFFICIENT EVIDENCE"}</Chip>
            <Chip tone="ok">Scoring vs peers {pitch.scoring_vs_peers_pct! >= 0 ? "+" : ""}{pitch.scoring_vs_peers_pct}%</Chip>
            <Chip tone="accent">Wickets vs peers {pitch.wickets_vs_peers_pct! >= 0 ? "+" : ""}{pitch.wickets_vs_peers_pct}%</Chip>
          </div>
          {pitch.style_evidence && <p className="text-[11px] text-fg-mute">Bowling-style evidence: {pitch.style_evidence.pace.balls} pace and {pitch.style_evidence.spin.balls} spin legal balls in this venue window.</p>}
          <div className="grid gap-2 sm:grid-cols-2">
            {pitch.last5 && <HistoryWindow title="Last 5" window={pitch.last5} />}
            {pitch.last10 && <HistoryWindow title="Last 10" window={pitch.last10} />}
          </div>
          <p className="text-[11px] text-fg-mute">As of {pitch.as_of} · Derived from <a className="underline" href="https://cricsheet.org/" target="_blank" rel="noreferrer">Cricsheet data</a> (<a className="underline" href="https://cricsheet.org/licensing/" target="_blank" rel="noreferrer">ODC Attribution licence</a>) · Team adjustments neutral{pitch.snapshot_fallback ? " · Last validated backup in use" : ""}.</p>
        </div>
      )}
    </div>
  );
}

export function WeatherInline({ weather }: { weather: Weather }) {
  if (weather.available === false) return <span className="text-fg-mute">Weather unavailable</span>;
  return (
    <span className="inline-flex items-center gap-1.5 text-fg-mute">
      <IconWind size={12} />
      <span className="mono-value">{Math.round(weather.temperature_c)}°C</span>
      <IconDroplet size={12} />
      <span className="mono-value">{weather.humidity_pct}%</span>
    </span>
  );
}
