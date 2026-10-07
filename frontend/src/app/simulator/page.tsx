"use client";

import { useEffect, useState } from "react";
import type { GenerateResponse } from "@/lib/types";
import { generateBestTeam, getTeams } from "@/lib/api";
import AnalysisResult, { AnalysisSkeleton } from "@/components/AnalysisResult";
import AppNav from "@/components/AppNav";
import { IconAlert, IconArrowRight } from "@/components/icons";
import { Button, Rivets, SectionLabel, Toggle } from "@/components/ui";

const FORMATS = ["T20", "ODI", "Test"] as const;
type Format = (typeof FORMATS)[number];

function tomorrowISO(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
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
  const [teams, setTeams] = useState<string[]>([]);
  const [venues, setVenues] = useState<string[]>([]);

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
    getTeams()
      .then((t) => {
        setTeams(t.teams);
        setVenues(t.venues);
      })
      .catch(() => {
        /* datalists stay empty; failures surface on submit */
      });
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
      <main className="flex-1 w-full max-w-7xl mx-auto px-5 md:px-8 py-8 md:py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-fg tracking-tight">Custom match simulator</h1>
          <p className="text-sm text-fg-mute mt-1.5">
            Any two teams, any venue, any format — the solver constructs the optimal XI.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-8 items-start">
          {/* ── Parameters ──────────────────────────────────────────── */}
          <div className="plate p-6 reveal">
            <Rivets />
            <SectionLabel accent className="mb-5">Match Parameters</SectionLabel>

            <div className="space-y-5">
              <div>
                <label htmlFor="team1" className="mono-label text-fg-mute block mb-1.5">Team A</label>
                <input
                  id="team1"
                  list="teams-list"
                  value={team1}
                  onChange={(e) => setTeam1(e.target.value)}
                  placeholder="India"
                  className="field w-full px-3 py-2.5 text-sm text-fg placeholder:text-fg-mute/60"
                />
              </div>

              <div>
                <label htmlFor="team2" className="mono-label text-fg-mute block mb-1.5">Team B</label>
                <input
                  id="team2"
                  list="teams-list"
                  value={team2}
                  onChange={(e) => setTeam2(e.target.value)}
                  placeholder="Australia"
                  className="field w-full px-3 py-2.5 text-sm text-fg placeholder:text-fg-mute/60"
                />
                {team1 && team2 && !canSubmit && (
                  <p className="text-xs text-warn mt-1.5">Choose different teams and a date from tomorrow onward.</p>
                )}
              </div>

              <datalist id="teams-list">
                {teams.map((t) => (
                  <option key={t} value={t} />
                ))}
              </datalist>

              <div>
                <label htmlFor="venue" className="mono-label text-fg-mute block mb-1.5">Venue</label>
                <input
                  id="venue"
                  list="venues-list"
                  value={venue}
                  onChange={(e) => setVenue(e.target.value)}
                  placeholder="Melbourne Cricket Ground"
                  className="field w-full px-3 py-2.5 text-sm text-fg placeholder:text-fg-mute/60"
                />
                <datalist id="venues-list">
                  {venues.map((v) => (
                    <option key={v} value={v} />
                  ))}
                </datalist>
                <p className="text-[11px] text-fg-mute mt-1.5">
                  Unknown venues fall back to a neutral pitch with geocoded weather.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="mono-label text-fg-mute block mb-1.5">Format</span>
                  <div className="field p-1 grid grid-cols-3 gap-1">
                    {FORMATS.map((f) => (
                      <button
                        key={f}
                        type="button"
                        onClick={() => setFormat(f)}
                        className={`mono-label !text-[10px] py-1.5 rounded-[3px] transition-colors ${
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
                    className="field w-full px-3 py-[9px] text-sm text-fg mono-value [color-scheme:dark]"
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
          <div id="sim-analysis" className="scroll-mt-20 space-y-6 min-w-0">
            {error && (
              <div className="flex items-start gap-2.5 text-sm text-danger bg-danger/5 border border-danger/25 rounded-md p-4">
                <IconAlert size={15} className="shrink-0 mt-0.5" />
                {error}
              </div>
            )}

            {loading && <AnalysisSkeleton label="Building squads → TriBE predictions → solver" />}

            {result && !loading && <AnalysisResult result={result} />}

            {!result && !loading && !error && (
              <div className="plate p-10 reveal">
                <Rivets />
                <FieldGraphic />
                <div className="text-center mt-6 max-w-sm mx-auto">
                  <SectionLabel className="mb-2">Awaiting Parameters</SectionLabel>
                  <p className="text-sm text-fg-dim leading-relaxed">
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
        <div className="max-w-7xl mx-auto px-5 md:px-8 h-12 flex items-center justify-between">
          <span className="mono-label text-fg-mute">NEW_X1 · Performance Intelligence Platform</span>
          <span className="mono-label text-fg-mute">Custom Simulation</span>
        </div>
      </footer>
    </div>
  );
}
