"use client";

import type { PlayerEntry } from "@/lib/types";
import { ENGINE_LABELS, ROLE_TONES } from "./RoleBadge";
import { Rivets } from "./ui";

interface Props {
  player: PlayerEntry;
  rank?: number;
  isCaptain?: boolean;
  isViceCaptain?: boolean;
}

export default function PlayerCard({ player, rank, isCaptain, isViceCaptain }: Props) {
  const engine = ENGINE_LABELS[player.engine] ?? ENGINE_LABELS.league_prior;
  const injured = ["INJURED", "RESTED", "SUSPENDED"].includes(player.injury_status);
  const doubtful = player.injury_status === "DOUBTFUL";
  const noHistory = player.matches_played === 0;

  return (
    <div
      className={`plate p-5 flex flex-col gap-3 transition-colors duration-150 h-full ${
        injured ? "opacity-60 border-danger/30" : "hover:border-fg-mute/60"
      }`}
    >
      <Rivets />

      {/* Identity */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          {rank !== undefined && (
            <span className="mono-value text-accent text-sm font-medium pt-0.5 tabular-nums">
              {String(rank).padStart(2, "0")}
            </span>
          )}
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
              <h3 className="font-semibold text-fg text-[15px] leading-tight truncate">
                {player.display_name}
              </h3>
              {isCaptain && (
                <span className="mono-label !text-[9px] bg-accent text-white px-1 py-px rounded-[3px] font-bold">
                  C
                </span>
              )}
              {isViceCaptain && (
                <span className="mono-label !text-[9px] border border-line text-fg-dim px-1 py-px rounded-[3px]">
                  VC
                </span>
              )}
            </div>
            <p className="text-[11px] text-fg-mute mt-0.5 truncate">{player.team}</p>
          </div>
        </div>
        <span
          className={`mono-label !text-[9px] border rounded-[3px] px-1.5 py-0.5 shrink-0 ${ROLE_TONES[player.role] ?? ROLE_TONES.BAT}`}
        >
          {player.role}
        </span>
      </div>

      {/* Projection */}
      <div className="flex items-end justify-between border-y border-line-soft py-3">
        <div>
          <div className="mono-value text-[26px] leading-none font-medium text-fg">
            {player.adjusted_score.toFixed(1)}
          </div>
          <div className="mono-label text-fg-mute mt-1.5">Proj. Pts</div>
        </div>
        <div className="text-right">
          <div className="mono-value text-sm text-fg-dim">
            {player.ci_low.toFixed(0)}–{player.ci_high.toFixed(0)}
          </div>
          <div className="mono-label text-fg-mute mt-1.5">80% Range</div>
        </div>
      </div>

      {/* Attributes */}
      <div className="flex flex-wrap gap-1.5">
        <span className={`mono-label !text-[9px] border rounded-[3px] px-1.5 py-0.5 ${engine.tone}`}>
          {engine.label}
        </span>
        {player.pitch_multiplier !== 1 && (
          <span className={`mono-label !text-[9px] border rounded-[3px] px-1.5 py-0.5 ${player.pitch_multiplier > 1 ? "text-ok border-ok/40" : "text-warn border-warn/40"}`}>
            Pitch ×{player.pitch_multiplier.toFixed(2)}
          </span>
        )}
        {doubtful && (
          <span className="mono-label !text-[9px] border border-warn/40 text-warn rounded-[3px] px-1.5 py-0.5">
            {player.injury_status} · {player.playing_probability}%
          </span>
        )}
        {injured && (
          <span className="mono-label !text-[9px] border border-danger/40 text-danger rounded-[3px] px-1.5 py-0.5">
            {player.injury_status}
          </span>
        )}
        {noHistory && (
          <span className="mono-label !text-[9px] border border-line-soft text-fg-mute rounded-[3px] px-1.5 py-0.5">
            No history · prior
          </span>
        )}
      </div>

      {/* Footer */}
      <div className="mono-label !text-[9px] text-fg-mute flex justify-between pt-0.5">
        <span>{player.matches_played} mts recorded</span>
        <span>
          Ceiling <span className="mono-value text-fg-dim">{player.captain_upside.toFixed(0)}</span>
        </span>
      </div>
    </div>
  );
}
