"use client";

import { ButtonHTMLAttributes, ReactNode } from "react";
import { IconCheck } from "./icons";

// ── Panel: plain raised card ────────────────────────────────────────────────

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`plate ${className}`}>{children}</div>;
}

// ── Section label ───────────────────────────────────────────────────────────

export function SectionLabel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <h2 className={`text-sm font-medium text-fg ${className}`}>{children}</h2>;
}

// ── Tag: quiet bordered text, color only when it carries meaning ────────────

export type ChipTone = "neutral" | "accent" | "ok" | "warn" | "danger";

const CHIP_TONES: Record<ChipTone, string> = {
  neutral: "text-fg-dim",
  accent: "text-accent",
  ok: "text-ok",
  warn: "text-warn",
  danger: "text-danger",
};

export function Chip({ children, tone = "neutral", className = "" }: { children: ReactNode; tone?: ChipTone; className?: string }) {
  return (
    <span className={`inline-flex items-center h-6 px-2 rounded-md border border-line text-xs whitespace-nowrap ${CHIP_TONES[tone]} ${className}`}>
      {children}
    </span>
  );
}

// ── Status dot (static) ─────────────────────────────────────────────────────

export function StatusDot({ tone = "ok", className = "" }: { tone?: "ok" | "warn" | "danger" | "mute"; className?: string }) {
  const color = { ok: "bg-ok", warn: "bg-warn", danger: "bg-danger", mute: "bg-fg-mute" }[tone];
  return <span className={`inline-block size-2 rounded-full shrink-0 ${color} ${className}`} />;
}

// ── Buttons ─────────────────────────────────────────────────────────────────

type ButtonVariant = "primary" | "outline" | "ghost" | "danger";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-fg text-accent-ink hover:bg-white",
  outline: "bg-transparent text-fg border border-line hover:bg-panel-hi",
  ghost: "bg-transparent text-fg-dim hover:text-fg hover:bg-panel-hi",
  danger: "bg-transparent text-danger border border-line hover:bg-danger/10",
};

export function Button({
  variant = "primary",
  className = "",
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 h-9 px-4 rounded-lg text-sm font-medium whitespace-nowrap transition-[background-color,color,transform] duration-150 ease-[var(--ease-out)] active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100 ${BUTTON_VARIANTS[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

// ── Toggle: switch row ──────────────────────────────────────────────────────

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
      className="flex items-center justify-between gap-4 w-full text-left disabled:opacity-50"
    >
      <span>
        <span className="block text-sm text-fg">{label}</span>
        {hint && <span className="block text-xs text-fg-mute mt-1">{hint}</span>}
      </span>
      <span className={`relative w-8 h-5 rounded-full shrink-0 transition-colors duration-150 ${checked ? "bg-accent" : "bg-panel-hi"}`}>
        <span
          className={`absolute top-0.5 left-0.5 size-4 rounded-full bg-fg transition-transform duration-150 ease-[var(--ease-out)] ${checked ? "translate-x-3" : "translate-x-0"}`}
        />
      </span>
    </button>
  );
}

// ── Checkbox row ────────────────────────────────────────────────────────────

export function CheckRow({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="checkbox" aria-checked={checked} onClick={() => onChange(!checked)} className="flex items-center gap-2 min-h-11 sm:min-h-8 group">
      <span
        className={`size-4 rounded border flex items-center justify-center transition-colors ${
          checked ? "bg-accent border-accent text-accent-ink" : "bg-field border-line text-transparent group-hover:border-fg-mute"
        }`}
      >
        <IconCheck size={12} />
      </span>
      <span className="text-sm text-fg-dim group-hover:text-fg transition-colors">{label}</span>
    </button>
  );
}

// ── Skeleton ────────────────────────────────────────────────────────────────

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

// ── Notice: one quiet line for warnings and errors ──────────────────────────

export function Notice({ tone = "warn", children }: { tone?: "warn" | "danger"; children: ReactNode }) {
  return (
    <div role="status" className="flex items-start gap-3 rounded-lg border border-line bg-panel px-4 py-3 text-sm text-fg-dim">
      <StatusDot tone={tone} className="mt-1.5" />
      <div className="min-w-0 break-words">{children}</div>
    </div>
  );
}

// ── Page header ─────────────────────────────────────────────────────────────

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl sm:text-[28px] leading-tight font-medium text-fg">{title}</h1>
        {subtitle && <p className="text-sm text-fg-dim mt-2 max-w-2xl">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

// ── Footer ──────────────────────────────────────────────────────────────────

export function SiteFooter() {
  return (
    <footer className="border-t border-line-soft mt-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-12 flex items-center justify-between gap-4 text-xs text-fg-mute">
        <span>NEW_X1</span>
        <span>
          Match data from{" "}
          <a className="underline underline-offset-2 hover:text-fg-dim" href="https://cricsheet.org/" target="_blank" rel="noreferrer">
            Cricsheet
          </a>
        </span>
      </div>
    </footer>
  );
}
