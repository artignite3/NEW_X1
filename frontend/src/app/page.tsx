import { connection } from "next/server";
import fs from "fs";
import path from "path";
import AppNav from "@/components/AppNav";
import FixturesBoard from "@/components/FixturesBoard";
import type { Match } from "@/lib/types";

function loadUpcomingMatches(): Match[] {
  try {
    const matchesPath = path.join(process.cwd(), "../data/future_matches/upcoming_matches.json");
    const data = fs.readFileSync(matchesPath, "utf8");
    return (JSON.parse(data).matches ?? []) as Match[];
  } catch (error) {
    console.error("Failed to load upcoming matches", error);
    return [];
  }
}

export default async function Home() {
  await connection();
  const matches = loadUpcomingMatches();

  return (
    <div className="min-h-screen flex flex-col">
      <AppNav />
      <main className="flex-1 w-full max-w-7xl mx-auto px-5 md:px-8 py-8 md:py-10">
        <FixturesBoard matches={matches} />
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
