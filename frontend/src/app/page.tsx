"use client";

import { useEffect, useState } from "react";
import AppNav from "@/components/AppNav";
import FixturesBoard from "@/components/FixturesBoard";
import { SiteFooter } from "@/components/ui";
import { getMatches } from "@/lib/api";
import type { Match } from "@/lib/types";

export default function Home() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [warning, setWarning] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getMatches().then((feed) => {
      if (!active) return;
      setMatches(Array.isArray(feed.matches) ? feed.matches : []);
      setWarning(feed.warning ?? null);
      setOffline(false);
    }).catch(() => {
      if (active) setOffline(true);
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <AppNav />
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
        <FixturesBoard matches={matches} feedWarning={warning} offline={offline} loading={loading} />
      </main>
      <SiteFooter />
    </div>
  );
}
