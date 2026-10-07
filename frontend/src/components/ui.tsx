"use client";

import { ButtonHTMLAttributes, ReactNode } from "react";
import { IconCheck } from "./icons";

// ── Plate: raised industrial panel with corner rivets ───────────────────────

export function Rivets() {
  return (
    <>
      <span className="rivet left-1.5 top-1.5" />
      <span className="rivet right-1.5 top-1.5" />
      <span className="rivet left-1.5 bottom-1.5" />
      <span className="rivet right-1.5 bottom-1.5" />
    </>
  );
}

export function Panel({
  children,
  className = "",
  rivets = true,
}: {
  children: ReactNode;
  className?: string;
  rivets?: boolean;
}) {
  return (
    <div className={`plate ${className}`}>
      {rivets && <Rivets />}
      {children}
    </div>
  );
}

// ── Section label: mono instrumentation heading ─────────────────────────────

export function SectionLabel({
  children,
  accent = false,
  className = "",
}: {
  children: ReactNode;
  accent?: boolean;
  className?: string;
}) {
  return (
    <div className={`mono-label ${accent ? "text-accent" : "text-fg-mute"} ${className}`}>
      {children}
    </div>
  );
}

// ── Chip: small bordered mono tag ───────────────────────────────────────────

export type ChipTone = "neutral" | "accent" | "ok" | "warn" | "danger";

const CHIP_TONES: Record<ChipTone, string> = {
  neutral: "border-line-soft text-fg-dim",
  accent: "border-accent/40 text-accent",
  ok: "border-ok/40 text-ok",
  warn: "border-warn/50 text-warn",
  danger: "border-danger/50 text-danger",
};

export function Chip({
  children,
  tone = "neutral",
  className = "",
}: {
  children: ReactNode;
  tone?: ChipTone;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 border rounded-[4px] px-1.5 py-0.5 mono-label !text-[9.5px] ${CHIP_TONES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

// ── Status dot ──────────────────────────────────────────────────────────────

export function StatusDot({
  tone = "ok",
  pulse = false,
  className = "",
}: {
  tone?: "ok" | "warn" | "danger" | "mute";
  pulse?: boolean;
  className?: string;
}) {
  const color = {
    ok: "bg-ok",
    warn: "bg-warn",
    danger: "bg-danger",
    mute: "bg-fg-mute",
  }[tone];
  const pulseClass = tone === "ok" ? "dot-pulse" : tone === "warn" ? "dot-pulse-amber" : "";
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full shrink-0 ${color} ${pulse ? pulseClass : ""} ${className}`}
    />
  );
}

// ── Buttons ─────────────────────────────────────────────────────────────────

type ButtonVariant = "primary" | "outline" | "ghost" | "danger";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-white border border-accent-hi/40 shadow-[inset_0_1px_0_rgba(255,255,255,0.22),0_1px_2px_rgba(0,0,0,0.4)] hover:bg-accent-hi active:shadow-[inset_0_2px_3px_rgba(0,0,0,0.25)]",
  outline:
    "bg-transparent text-fg-dim border border-line hover:border-accent/60 hover:text-accent active:bg-accent/5",
  ghost: "bg-transparent text-fg-dim border border-transparent hover:text-fg hover:bg-white/5",
  danger:
    "bg-transparent text-danger border border-danger/40 hover:bg-danger/10 active:bg-danger/15",
};

export function Button({
  variant = "primary",
  className = "",
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-[5px] mono-label !tracking-[0.14em] px-4 py-2.5 transition-all duration-150 disabled:opacity-45 disabled:cursor-not-allowed ${BUTTON_VARIANTS[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

// ── Toggle: formal switch row ───────────────────────────────────────────────

export function Toggle({
  checked,
  onChange,
  label,
  hint,
  disabled = false,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  hint?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="flex items-center justify-between gap-4 w-full text-left group disabled:opacity-50"
    >
      <span>
        <span className="block mono-label text-fg-dim group-hover:text-fg transition-colors">
          {label}
        </span>
        {hint && <span className="block text-[11px] text-fg-mute mt-0.5">{hint}</span>}
      </span>
      <span
        className={`relative w-8 h-[18px] rounded-full border shrink-0 transition-colors duration-150 ${
          checked ? "bg-accent/25 border-accent/60" : "bg-field border-line"
        }`}
      >
        <span
          className={`absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full transition-all duration-150 ${
            checked
              ? "left-[16px] bg-accent shadow-[0_0_6px_rgba(240,86,29,0.5)]"
              : "left-[2px] bg-fg-mute"
          }`}
        />
      </span>
    </button>
  );
}

// ── Checkbox row (compact, mono) ────────────────────────────────────────────

export function CheckRow({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="flex items-center gap-2 group"
    >
      <span
        className={`w-[15px] h-[15px] rounded-[3px] border flex items-center justify-center transition-colors ${
          checked ? "bg-accent/20 border-accent/70 text-accent" : "bg-field border-line text-transparent group-hover:border-fg-mute"
        }`}
      >
        <IconCheck size={10} className="stroke-[2.5]" />
      </span>
      <span className="mono-label text-fg-dim group-hover:text-fg transition-colors">{label}</span>
    </button>
  );
}

// ── Skeleton ────────────────────────────────────────────────────────────────

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

// ── Indeterminate progress ──────────────────────────────────────────────────

export function Progress() {
  return <div className="progress-bar w-full" aria-label="Loading" />;
}
