import { connection } from "next/server";
import fs from "fs";
import path from "path";
import AppNav from "@/components/AppNav";
import FixturesBoard from "@/components/FixturesBoard";
import type { Match } from "@/lib/types";

interface FixtureFeed { matches: Match[]; warning: string | null; }

function parseFeed(file: string): FixtureFeed {
  const parsed: unknown = JSON.parse(fs.readFileSync(file, "utf8"));
  if (typeof parsed !== "object" || parsed === null || !("matches" in parsed) || !Array.isArray(parsed.matches) ||
      !("fetched_at" in parsed) || typeof parsed.fetched_at !== "string" ||
      !("source" in parsed) || typeof parsed.source !== "string") {
    throw new Error("Invalid fixture feed");
  }
  const fetched = Date.parse(parsed.fetched_at);
  if (!Number.isFinite(fetched)) throw new Error("Invalid fixture timestamp");
  const seen = new Set<string>();
  const matches = parsed.matches.filter((item: unknown): item is Match => {
    if (typeof item !== "object" || item === null) throw new Error("Invalid fixture entry");
    const m = item as Partial<Match>;
    if (!m.match_id || !m.date || !/^\d{4}-\d{2}-\d{2}$/.test(m.date) ||
        !m.team1 || !m.team2 || !["T20", "ODI", "TEST"].includes(String(m.match_type).toUpperCase())) {
      throw new Error("Incomplete fixture entry");
    }
    const id = String(m.match_id);
    if (seen.has(id)) throw new Error("Duplicate fixture ID");
    seen.add(id);
    return true;
  });
  const today = new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
  return { matches: matches.filter((m) => m.date > today && !m.match_ended && !m.status?.toLowerCase().includes("ended")),
           warning: Date.now() - fetched > 86_400_000 ? "Fixture feed was last refreshed over 24 hours ago. Confirm match details before analysis." : null };
}

function loadUpcomingMatches(): FixtureFeed {
  const dir = path.join(process.cwd(), "../data/future_matches");
  try {
    return parseFeed(path.join(dir, "upcoming_matches.json"));
  } catch {
    try {
      return { ...parseFeed(path.join(dir, "upcoming_matches.last_good.json")),
               warning: "Fixture feed is unavailable. Showing the last validated snapshot; confirm match details before analysis." };
    } catch {
      return { matches: [], warning: "Fixture feed unavailable. No verified backup is present." };
    }
  }
}

export default async function Home() {
  await connection();
  const feed = loadUpcomingMatches();

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
