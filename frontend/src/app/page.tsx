import { connection } from "next/server";
import AppNav from "@/components/AppNav";
import FixturesBoard from "@/components/FixturesBoard";
import type { Match } from "@/lib/types";

interface FixtureFeed { matches: Match[]; warning: string | null; }

async function loadUpcomingMatches(): Promise<FixtureFeed> {
  const base = process.env.API_INTERNAL_BASE ?? process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
  try {
    const response = await fetch(`${base}/matches`, {
      cache: "no-store", signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) throw new Error("Fixture API unavailable");
    const feed = await response.json();
    if (!Array.isArray(feed.matches)) throw new Error("Invalid fixture response");
    return { matches: feed.matches, warning: typeof feed.warning === "string" ? feed.warning : null };
  } catch {
    return { matches: [], warning: "Fixtures are temporarily unavailable. Please try again shortly." };
  }
}

export default async function Home() {
  await connection();
  const feed = await loadUpcomingMatches();

  return (
    <div className="min-h-screen flex flex-col">
      <AppNav />
      <main className="flex-1 w-full max-w-7xl mx-auto px-5 md:px-8 py-8 md:py-10">
        <FixturesBoard matches={feed.matches} feedWarning={feed.warning} />
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
