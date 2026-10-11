"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { GenerateResponse } from "@/lib/types";
import { generateBestTeam, getTeams } from "@/lib/api";
import AnalysisResult, { AnalysisSkeleton } from "@/components/AnalysisResult";
import AppNav from "@/components/AppNav";
import { IconAlert, IconArrowRight, IconCheck, IconCross } from "@/components/icons";
import { Button, Rivets, SectionLabel, Toggle } from "@/components/ui";

const FORMATS = ["T20", "ODI", "Test"] as const;
type Format = (typeof FORMATS)[number];

const DEFAULT_TEAMS: string[] = [
  "Afghanistan",
  "Australia",
  "Australia Women",
  "Bangladesh",
  "Bangladesh Women",
  "England",
  "England Women",
  "India",
  "India Women",
  "Ireland",
  "Ireland Women",
  "Namibia",
  "Nepal",
  "Netherlands",
  "New Zealand",
  "New Zealand Women",
  "Oman",
  "Pakistan",
  "Pakistan Women",
  "Papua New Guinea",
  "Scotland",
  "South Africa",
  "South Africa Women",
  "Sri Lanka",
  "Sri Lanka Women",
  "United Arab Emirates",
  "United States of America",
  "West Indies",
  "West Indies Women",
  "Zimbabwe",
  "Zimbabwe Women",
];

const DEFAULT_VENUES: string[] = [
  "Adelaide Oval",
  "Arun Jaitley Stadium, Delhi",
  "Barsapara Cricket Stadium, Guwahati",
  "Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium, Lucknow",
  "Brabourne Stadium, Mumbai",
  "Darren Sammy National Cricket Stadium, Gros Islet",
  "Dubai International Cricket Stadium",
  "Eden Gardens, Kolkata",
  "Eden Park, Auckland",
  "Edgbaston, Birmingham",
  "Gaddafi Stadium, Lahore",
  "Galle International Stadium",
  "Hagley Oval, Christchurch",
  "Headingley, Leeds",
  "Holkar Cricket Stadium, Indore",
  "Kensington Oval, Bridgetown",
  "Kennington Oval, London",
  "Lord's, London",
  "M Chinnaswamy Stadium, Bengaluru",
  "MA Chidambaram Stadium, Chennai",
  "Melbourne Cricket Ground",
  "Narendra Modi Stadium, Ahmedabad",
  "Newlands, Cape Town",
  "Old Trafford, Manchester",
  "Pallekele International Cricket Stadium",
  "Perth Stadium",
  "Premadasa Stadium, Colombo",
  "Queen's Park Oval, Port of Spain",
  "Rajiv Gandhi International Stadium, Hyderabad",
  "Rawalpindi Cricket Stadium",
  "Sabina Park, Kingston",
  "Sawai Mansingh Stadium, Jaipur",
  "Seddon Park, Hamilton",
  "Sharjah Cricket Stadium",
  "Sher-e-Bangla National Cricket Stadium, Mirpur",
  "SuperSport Park, Centurion",
  "Sydney Cricket Ground",
  "The Gabba, Brisbane",
  "The Rose Bowl, Southampton",
  "The Wanderers Stadium, Johannesburg",
  "Trent Bridge, Nottingham",
  "Wankhede Stadium, Mumbai",
  "Zayed Cricket Stadium, Abu Dhabi",
];

function mergeSorted(defaults: string[], incoming: string[]): string[] {
  const byCf = new Map<string, string>();
  for (const item of [...defaults, ...incoming]) {
    const trimmed = item?.trim();
    if (!trimmed) continue;
    const key = trimmed.toLowerCase();
    if (!byCf.has(key)) byCf.set(key, trimmed);
  }
  return Array.from(byCf.values()).sort((a, b) => a.localeCompare(b));
}

function tomorrowISO(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

interface ComboboxProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
  placeholder?: string;
  excludeValue?: string;
}

function Combobox({
  id,
  label,
  value,
  onChange,
  options,
  placeholder,
  excludeValue,
}: ComboboxProps) {
  const [open, setOpen] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const filtered = useMemo(() => {
    const ex = excludeValue?.trim().toLowerCase();
    const available = ex ? options.filter((o) => o.toLowerCase() !== ex) : options;
    const query = isTyping ? value.trim().toLowerCase() : "";
    if (!query) return available;
    const startsWith: string[] = [];
    const includes: string[] = [];
    for (const opt of available) {
      const lower = opt.toLowerCase();
      if (lower.startsWith(query)) startsWith.push(opt);
      else if (lower.includes(query)) includes.push(opt);
    }
    return [...startsWith, ...includes];
  }, [options, value, isTyping, excludeValue]);

  useEffect(() => {
    const onPointerDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setIsTyping(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  useEffect(() => {
    if (!open || !listRef.current) return;
    const item = listRef.current.children[activeIndex] as HTMLElement | undefined;
    item?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, open]);

  const selectOption = (opt: string) => {
    onChange(opt);
    setIsTyping(false);
    setOpen(false);
  };

  const openMenu = () => {
    setOpen(true);
    setIsTyping(false);
    const idx = filtered.findIndex((o) => o.toLowerCase() === value.trim().toLowerCase());
    setActiveIndex(idx >= 0 ? idx : 0);
  };

  return (
    <div ref={containerRef} className="relative">
      <label htmlFor={id} className="mono-label text-fg-mute block mb-1.5">
        {label}
      </label>
      <div className="relative flex items-center">
        <input
          ref={inputRef}
          id={id}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={`${id}-listbox`}
          aria-autocomplete="list"
          autoComplete="off"
          value={value}
          placeholder={placeholder}
          onFocus={openMenu}
          onClick={openMenu}
          onChange={(e) => {
            onChange(e.target.value);
            setIsTyping(true);
            setOpen(true);
            setActiveIndex(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              if (!open) {
                openMenu();
              } else if (filtered.length > 0) {
                setActiveIndex((prev) => (prev + 1) % filtered.length);
              }
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              if (!open) {
                openMenu();
              } else if (filtered.length > 0) {
                setActiveIndex((prev) => (prev - 1 + filtered.length) % filtered.length);
              }
            } else if (e.key === "Enter" && open && filtered[activeIndex]) {
              e.preventDefault();
              selectOption(filtered[activeIndex]);
            } else if (e.key === "Escape") {
              setOpen(false);
              setIsTyping(false);
            } else if (e.key === "Tab") {
              setOpen(false);
              setIsTyping(false);
            }
          }}
          className="field w-full pl-3 pr-14 py-2.5 text-sm text-fg placeholder:text-fg-mute/60"
        />
        <div className="absolute right-1.5 inset-y-0 flex items-center gap-0.5">
          {value && (
            <button
              type="button"
              tabIndex={-1}
              aria-label={`Clear ${label}`}
              onClick={(e) => {
                e.stopPropagation();
                onChange("");
                setIsTyping(false);
                setOpen(true);
                setActiveIndex(0);
                inputRef.current?.focus();
              }}
              className="p-1 text-fg-mute hover:text-fg transition-colors rounded"
            >
              <IconCross size={12} />
            </button>
          )}
          <button
            type="button"
            tabIndex={-1}
            aria-label={`Toggle ${label} options`}
            onClick={(e) => {
              e.stopPropagation();
              if (open) {
                setOpen(false);
                setIsTyping(false);
              } else {
                openMenu();
                inputRef.current?.focus();
              }
            }}
            className="p-1.5 text-fg-mute hover:text-fg transition-colors rounded"
          >
            <svg
              width={12}
              height={12}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              className={`transition-transform duration-150 ${open ? "rotate-180 text-accent" : ""}`}
              aria-hidden
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
        </div>
      </div>

      {open && (
        <ul
          ref={listRef}
          id={`${id}-listbox`}
          role="listbox"
          className="absolute z-50 left-0 right-0 mt-1.5 max-h-60 overflow-y-auto rounded-[5px] border border-line bg-[#121215] shadow-[0_12px_28px_rgba(0,0,0,0.75)] py-1"
        >
          {filtered.length === 0 ? (
            <li className="px-3 py-2.5 text-xs text-fg-mute mono-value">
              No matching options — custom value will be used.
            </li>
          ) : (
            filtered.map((opt, idx) => {
              const selected = opt.toLowerCase() === value.trim().toLowerCase();
              const active = idx === activeIndex;
              return (
                <li
                  key={opt}
                  role="option"
                  aria-selected={selected}
                  onMouseEnter={() => setActiveIndex(idx)}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    selectOption(opt);
                  }}
                  className={`px-3 py-2 text-sm cursor-pointer flex items-center justify-between gap-2 transition-colors ${
                    active
                      ? "bg-accent/15 text-fg"
                      : selected
                      ? "bg-white/[0.04] text-accent"
                      : "text-fg-dim hover:bg-white/[0.04] hover:text-fg"
                  }`}
                >
                  <span className="truncate">{opt}</span>
                  {selected && <IconCheck size={13} className="text-accent shrink-0" />}
                </li>
              );
            })
          )}
        </ul>
      )}
    </div>
  );
}

// Abstract field diagram — the empty-state graphic doubles as a product metaphor
function FieldGraphic() {
  return (
    <svg viewBox="0 0 320 180" className="w-full max-w-md mx-auto" aria-hidden>
      {/* boundary */}
      <ellipse cx="160" cy="90" rx="150" ry="82" fill="none" stroke="#26262a" strokeWidth="1.5" />
      <ellipse cx="160" cy="90" rx="120" ry="64" fill="none" stroke="#1d1d21" strokeWidth="1" />
      {/* 30-yard circle */}
      <ellipse cx="160" cy="90" rx="78" ry="42" fill="none" stroke="#1d1d21" strokeWidth="1" strokeDasharray="3 4" />
      {/* pitch */}
      <rect x="148" y="66" width="24" height="48" rx="2" fill="#141416" stroke="#26262a" strokeWidth="1" />
      {/* trajectory */}
      <path d="M160 110 C 120 60, 200 50, 236 66" fill="none" stroke="#f0561d" strokeWidth="1.5"
        className="draw-line" style={{ ["--dash" as string]: "160" }} />
      <circle cx="160" cy="110" r="2.5" fill="#f0561d" />
      <circle cx="236" cy="66" r="2" fill="none" stroke="#f0561d" strokeWidth="1.5" />
      {/* crosshair ticks */}
      <path d="M160 4v10M160 166v10M6 90h10M304 90h10" stroke="#26262a" strokeWidth="1" />
    </svg>
  );
}

export default function SimulatorPage() {
  const [teams, setTeams] = useState<string[]>(DEFAULT_TEAMS);
  const [venues, setVenues] = useState<string[]>(DEFAULT_VENUES);

  const [team1, setTeam1] = useState("");
  const [team2, setTeam2] = useState("");
  const [venue, setVenue] = useState("");
  const [format, setFormat] = useState<Format>("T20");
  const [date, setDate] = useState(tomorrowISO);
  const [scanNews, setScanNews] = useState(false);
  const [useMl, setUseMl] = useState(true);
  const [useIntelligence, setUseIntelligence] = useState(true);
  const [riskAversion, setRiskAversion] = useState(0.05);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GenerateResponse | null>(null);

  useEffect(() => {
    let active = true;
    let retryTimer: number | undefined;

    const loadCatalog = async (attempt = 0) => {
      try {
        const t = await getTeams();
        if (!active) return;
        if (Array.isArray(t.teams) && t.teams.length > 0) {
          setTeams(mergeSorted(DEFAULT_TEAMS, t.teams));
        }
        if (Array.isArray(t.venues) && t.venues.length > 0) {
          setVenues(mergeSorted(DEFAULT_VENUES, t.venues));
        }
      } catch {
        if (active && attempt < 2) {
          retryTimer = window.setTimeout(() => void loadCatalog(attempt + 1), 2000 * (attempt + 1));
        }
      }
    };

    const handleRefresh = () => void loadCatalog(0);
    void loadCatalog(0);
    window.addEventListener("new_x1_api_base_changed", handleRefresh);
    window.addEventListener("focus", handleRefresh);
    return () => {
      active = false;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      window.removeEventListener("new_x1_api_base_changed", handleRefresh);
      window.removeEventListener("focus", handleRefresh);
    };
  }, []);

  const canSubmit =
    team1.trim().length > 0 &&
    team2.trim().length > 0 &&
    team1.trim().toLowerCase() !== team2.trim().toLowerCase() && date >= tomorrowISO();

  const run = async () => {
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await generateBestTeam({
        team1: team1.trim(),
        team2: team2.trim(),
        format,
        venue: venue.trim() || undefined,
        date,
        use_ml: useMl,
        use_intelligence: useIntelligence,
        risk_aversion: riskAversion,
        scan_news: scanNews,
      });
      setResult(res);
      setTimeout(() => document.getElementById("sim-analysis")?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Simulation failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <AppNav />
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 md:py-10">
        <div className="mb-6 sm:mb-8">
          <h1 className="text-xl sm:text-2xl font-semibold text-fg tracking-tight">Custom match simulator</h1>
          <p className="text-xs sm:text-sm text-fg-mute mt-1.5 leading-relaxed">
            Any two teams, any venue, any format — the solver constructs the optimal XI.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] xl:grid-cols-[380px_1fr] gap-6 lg:gap-8 items-start">
          {/* ── Parameters ──────────────────────────────────────────── */}
          <div className="plate p-4 sm:p-6 reveal">
            <Rivets />
            <SectionLabel accent className="mb-4 sm:mb-5">Match Parameters</SectionLabel>

            <div className="space-y-4 sm:space-y-5">
              <Combobox
                id="team1"
                label="Team A"
                value={team1}
                onChange={setTeam1}
                options={teams}
                excludeValue={team2}
                placeholder="Select or type Team A (e.g. India)"
              />

              <div>
                <Combobox
                  id="team2"
                  label="Team B"
                  value={team2}
                  onChange={setTeam2}
                  options={teams}
                  excludeValue={team1}
                  placeholder="Select or type Team B (e.g. Australia)"
                />
                {team1 && team2 && !canSubmit && (
                  <p className="text-xs text-warn mt-1.5">Choose different teams and a date from tomorrow onward.</p>
                )}
              </div>

              <div>
                <Combobox
                  id="venue"
                  label="Venue"
                  value={venue}
                  onChange={setVenue}
                  options={venues}
                  placeholder="Select or type Venue (e.g. Melbourne Cricket Ground)"
                />
                <p className="text-[11px] text-fg-mute mt-1.5">
                  Unknown venues fall back to a neutral pitch with geocoded weather.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-4">
                <div>
                  <span className="mono-label text-fg-mute block mb-1.5">Format</span>
                  <div className="field p-1 grid grid-cols-3 gap-1">
                    {FORMATS.map((f) => (
                      <button
                        key={f}
                        type="button"
                        onClick={() => setFormat(f)}
                        className={`mono-label !text-[10px] py-2 sm:py-1.5 rounded-[3px] transition-colors ${
                          format === f
                            ? "bg-accent/15 text-accent border border-accent/40"
                            : "text-fg-mute hover:text-fg-dim border border-transparent"
                        }`}
                      >
                        {f.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label htmlFor="date" className="mono-label text-fg-mute block mb-1.5">Match Date</label>
                  <input
                    id="date"
                    type="date"
                    min={tomorrowISO()}
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                    className="field w-full px-3 py-2 sm:py-[9px] text-sm text-fg mono-value [color-scheme:dark]"
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between items-baseline mb-1.5">
                  <span className="mono-label text-fg-mute">Risk Aversion</span>
                  <span className="mono-value text-xs text-accent">λ = {riskAversion.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="0.2"
                  step="0.01"
                  value={riskAversion}
                  onChange={(e) => setRiskAversion(parseFloat(e.target.value))}
                  className="w-full accent-[var(--color-accent)]"
                />
                <div className="flex justify-between mono-label !text-[8.5px] text-fg-mute mt-1">
                  <span>Ceiling</span>
                  <span>Safety</span>
                </div>
              </div>

              <div className="border-t border-line-soft pt-4 space-y-3.5">
                <Toggle checked={useMl} onChange={setUseMl} label="ML predictions" hint="CatBoost for T20; TriBE ensemble for ODI and Test" />
                <Toggle checked={scanNews} onChange={setScanNews} label="Scan injury news" hint="Check headlines mentioning the selected squad" />
                <Toggle checked={useIntelligence} onChange={setUseIntelligence} label="Match intelligence" hint="Weather, pitch profile, injury status" />
              </div>

              <Button onClick={run} disabled={!canSubmit || loading} className="w-full">
                {loading ? "Simulating" : "Generate Optimal XI"}
                <IconArrowRight size={13} />
              </Button>
            </div>
          </div>

          {/* ── Result ──────────────────────────────────────────────── */}
          <div id="sim-analysis" className="scroll-mt-24 space-y-6 min-w-0">
            {error && (
              <div className="flex items-start gap-2.5 text-xs sm:text-sm text-danger bg-danger/5 border border-danger/25 rounded-md p-3.5 sm:p-4">
                <IconAlert size={15} className="shrink-0 mt-0.5" />
                <span className="min-w-0 break-words">{error}</span>
              </div>
            )}

            {loading && <AnalysisSkeleton label="Building squads → TriBE predictions → solver" />}

            {result && !loading && <AnalysisResult result={result} />}

            {!result && !loading && !error && (
              <div className="plate p-6 sm:p-10 reveal">
                <Rivets />
                <FieldGraphic />
                <div className="text-center mt-5 sm:mt-6 max-w-sm mx-auto">
                  <SectionLabel className="mb-2">Awaiting Parameters</SectionLabel>
                  <p className="text-xs sm:text-sm text-fg-dim leading-relaxed">
                    Configure a hypothetical match on the left. The engine assembles each team&apos;s
                    best-known squad, predicts every player with the format-specific model, and solves for
                    the risk-adjusted optimal XI.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
      <footer className="border-t border-line-soft">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 sm:h-12 flex flex-wrap items-center justify-between gap-2">
          <span className="mono-label text-fg-mute">NEW_X1 · Performance Intelligence Platform</span>
          <span className="mono-label text-fg-mute">Custom Simulation</span>
        </div>
      </footer>
    </div>
  );
}
