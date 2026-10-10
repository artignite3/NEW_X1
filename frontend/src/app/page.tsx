"use client";

import { useEffect, useState } from "react";
import AppNav from "@/components/AppNav";
import FixturesBoard from "@/components/FixturesBoard";
import { getMatches } from "@/lib/api";
import type { Match } from "@/lib/types";

export default function Home() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [warning, setWarning] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getMatches().then((feed) => {
      if (!active) return;
      setMatches(Array.isArray(feed.matches) ? feed.matches : []);
      setWarning(feed.warning ?? null);
    }).catch((error) => {
      if (active) setWarning(error instanceof Error ? error.message : "Fixtures are temporarily unavailable.");
    });
    return () => { active = false; };
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <AppNav />
      <main className="flex-1 w-full max-w-7xl mx-auto px-5 md:px-8 py-8 md:py-10">
        <FixturesBoard matches={matches} feedWarning={warning} />
      </main>
      <footer className="border-t border-line-soft">
        <div className="max-w-7xl mx-auto px-5 md:px-8 h-12 flex items-center justify-between">
          <span className="mono-label text-fg-mute">NEW_X1 · Performance Intelligence Platform</span>
          <span className="mono-label text-fg-mute">T20 / ODI / Test</span>
        </div>
      </footer>
    </div>
  );
}
