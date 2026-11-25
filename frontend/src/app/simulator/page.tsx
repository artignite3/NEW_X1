"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { GenerateResponse } from "@/lib/types";
import { generateBestTeam, getTeams } from "@/lib/api";
import AnalysisResult, { AnalysisSkeleton } from "@/components/AnalysisResult";
import AppNav from "@/components/AppNav";
import { IconCheck, IconCross } from "@/components/icons";
import OvalGraphic from "@/components/OvalGraphic";
import { Button, Notice, PageHeader, SiteFooter, Toggle } from "@/components/ui";

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
      <label htmlFor={id} className="text-sm text-fg-dim block mb-2">
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
          className="field w-full h-10 pl-3 pr-16 text-sm text-fg placeholder:text-fg-mute"
        />
        <div className="absolute right-2 inset-y-0 flex items-center gap-1">
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
              <IconCross size={14} />
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
            className="p-1 text-fg-mute hover:text-fg transition-colors rounded"
          >
            <svg
              width={16}
              height={16}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
              className={`transition-transform duration-150 ${open ? "rotate-180" : ""}`}
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
          className="absolute z-50 left-0 right-0 mt-2 max-h-60 overflow-y-auto rounded-lg border border-line bg-panel-hi shadow-[var(--shadow-menu)] p-1"
        >
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-sm text-fg-mute">
              No match in the list, your entry will be used as typed
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
                  className={`h-8 px-3 rounded-md text-sm cursor-pointer flex items-center justify-between gap-2 transition-colors ${
                    active ? "bg-white/[0.06] text-fg" : selected ? "text-fg" : "text-fg-dim"
                  }`}
                >
                  <span className="truncate">{opt}</span>
                  {selected && <IconCheck size={16} className="text-accent shrink-0" />}
                </li>
              );
            })
          )}
        </ul>
      )}
    </div>
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
      setError(e instanceof Error ? e.message : "Team selection could not be generated");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <AppNav />
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
        <PageHeader
          title="Custom match"
          subtitle="Choose any two teams, a venue, format and date to get the best XI for that match"
        />

        <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-8 items-start mt-8">
          {/* ── Parameters ──────────────────────────────────────────── */}
          <div className="plate p-6 space-y-6">
            <div className="space-y-4">
              <Combobox
                id="team1"
                label="First team"
                value={team1}
                onChange={setTeam1}
                options={teams}
                excludeValue={team2}
                placeholder="India"
              />

              <div>
                <Combobox
                  id="team2"
                  label="Second team"
                  value={team2}
                  onChange={setTeam2}
                  options={teams}
                  excludeValue={team1}
                  placeholder="Australia"
                />
                {team1 && team2 && !canSubmit && (
                  <p className="text-xs text-warn mt-2">Choose two different teams and a date from tomorrow onward</p>
                )}
              </div>

              <div>
                <Combobox
                  id="venue"
                  label="Venue"
                  value={venue}
                  onChange={setVenue}
                  options={venues}
                  placeholder="Melbourne Cricket Ground"
                />
                <p className="text-xs text-fg-mute mt-2">An unknown venue uses a neutral pitch and its local weather</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-4">
                <div>
                  <span className="text-sm text-fg-dim block mb-2">Format</span>
                  <div className="field p-1 grid grid-cols-3 gap-1" role="radiogroup" aria-label="Format">
                    {FORMATS.map((f) => (
                      <button
                        key={f}
                        type="button"
                        role="radio"
                        aria-checked={format === f}
                        onClick={() => setFormat(f)}
                        className={`h-8 rounded-md text-sm transition-colors ${
                          format === f ? "bg-panel-hi text-fg ring-1 ring-inset ring-line" : "text-fg-mute hover:text-fg"
                        }`}
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label htmlFor="date" className="text-sm text-fg-dim block mb-2">Match date</label>
                  <input
                    id="date"
                    type="date"
                    min={tomorrowISO()}
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                    className="field w-full h-10 px-3 text-sm text-fg mono-value [color-scheme:dark]"
                  />
                </div>
              </div>
            </div>

            <div className="pt-6 border-t border-line-soft">
              <div className="flex justify-between items-baseline">
                <label htmlFor="risk" className="text-sm text-fg-dim">Risk appetite</label>
                <span className="mono-value text-sm text-fg">λ {riskAversion.toFixed(2)}</span>
              </div>
              <input
                id="risk"
                type="range"
                min="0"
                max="0.2"
                step="0.01"
                value={riskAversion}
                onChange={(e) => setRiskAversion(parseFloat(e.target.value))}
                className="w-full mt-2 accent-[var(--color-accent)]"
              />
              <div className="flex justify-between text-xs text-fg-mute mt-1">
                <span>Chase upside</span>
                <span>Play safe</span>
              </div>
            </div>

            <div className="pt-6 border-t border-line-soft space-y-4">
              <Toggle checked={useMl} onChange={setUseMl} label="Model predictions" hint="CatBoost for T20, TriBE ensemble for ODI and Test" />
              <Toggle checked={useIntelligence} onChange={setUseIntelligence} label="Weather and pitch" hint="Adjust for conditions, pitch profile and injuries" />
              <Toggle checked={scanNews} onChange={setScanNews} label="Injury news" hint="Check recent headlines for the selected squads, slower" />
            </div>

            <Button onClick={run} disabled={!canSubmit || loading} className="w-full">
              {loading ? "Picking the XI" : "Pick best XI"}
            </Button>
          </div>

          {/* ── Result ──────────────────────────────────────────────── */}
          <div id="sim-analysis" className="scroll-mt-24 space-y-6 min-w-0">
            {error && <Notice tone="danger">{error}</Notice>}

            {loading && <AnalysisSkeleton label="Building squads, predicting players and solving for the best XI" />}

            {result && !loading && <AnalysisResult result={result} />}

            {!result && !loading && !error && (
              <div className="plate px-6 py-12 flex flex-col items-center text-center">
                <OvalGraphic />
                <h2 className="text-base font-medium text-fg mt-6">Set up a match to see its best XI</h2>
                <p className="text-sm text-fg-dim mt-2 max-w-md">
                  Each team&apos;s latest known squad is scored with the model for that format, then the solver picks
                  the eleven with the best projected total for your risk appetite
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
