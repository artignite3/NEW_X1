import fs from 'fs';
import path from 'path';

export default function Home() {
  // Read upcoming matches from the data directory
  const matchesPath = path.join(process.cwd(), '../data/future_matches/upcoming_matches.json');
  let upcomingMatches = [];
  try {
    const data = fs.readFileSync(matchesPath, 'utf8');
    upcomingMatches = JSON.parse(data).matches || [];
  } catch (error) {
    console.error("Failed to load upcoming matches", error);
  }

  // Filter to tomorrow onwards
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  
  const futureMatches = upcomingMatches.filter((m: any) => {
    const mDate = new Date(m.date);
    return mDate > today;
  });

  const todayMatches = upcomingMatches.filter((m: any) => {
    const mDate = new Date(m.date);
    return mDate.getTime() === today.getTime();
  });

  return (
    <main className="min-h-screen bg-gray-950 text-slate-100 p-8 font-sans">
      <div className="max-w-6xl mx-auto">
        <header className="bg-gradient-to-br from-gray-900 to-slate-800 border border-slate-700 rounded-xl p-8 mb-8 flex justify-between items-center shadow-lg">
          <div>
            <h1 className="text-4xl font-extrabold bg-gradient-to-r from-sky-400 to-emerald-400 bg-clip-text text-transparent">
              NEW_X1 — Cricket Intelligence
            </h1>
            <p className="text-slate-400 mt-2">Next.js Optimized Performance Platform</p>
          </div>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Sidebar */}
          <div className="md:col-span-1 space-y-6">
            <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
              <h2 className="text-xl font-bold mb-4">🎯 Mode Selection</h2>
              <div className="space-y-3">
                <label className="flex items-center space-x-3 cursor-pointer">
                  <input type="radio" name="mode" defaultChecked className="text-sky-500 bg-gray-800 border-gray-700 focus:ring-sky-500" />
                  <span>🔮 Upcoming Fixtures</span>
                </label>
                <label className="flex items-center space-x-3 cursor-pointer">
                  <input type="radio" name="mode" className="text-sky-500 bg-gray-800 border-gray-700 focus:ring-sky-500" />
                  <span>⚙️ Custom Simulator</span>
                </label>
              </div>
            </div>

            {todayMatches.length > 0 && (
              <div className="bg-blue-900/30 border border-blue-800/50 rounded-xl p-4 text-blue-200">
                <div className="font-bold mb-2">🏏 Today's Matches ({todayMatches.length})</div>
                <div className="text-sm">Awaiting Toss (T-30 min) for final XI prediction.</div>
              </div>
            )}
          </div>

          {/* Main Content Area */}
          <div className="md:col-span-3">
            <h2 className="text-2xl font-bold mb-6">Upcoming Matches</h2>
            <div className="grid grid-cols-1 gap-4">
              {futureMatches.map((match: any, idx: number) => (
                <div key={idx} className="bg-gray-900 border border-gray-800 rounded-xl p-6 hover:border-sky-500 transition-colors shadow-sm cursor-pointer flex justify-between items-center">
                  <div>
                    <span className="text-xs font-bold px-2 py-1 bg-purple-600 rounded-full uppercase tracking-wider">
                      {match.match_type} FORMAT
                    </span>
                    <h3 className="text-xl font-bold mt-3 text-white">
                      {match.team1} <span className="text-sky-400 font-normal">VS</span> {match.team2}
                    </h3>
                    <p className="text-slate-400 text-sm mt-1">
                      📍 {match.venue} • 🏆 {match.series.substring(0, 30)}
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-semibold text-slate-300">{match.date}</div>
                    <button className="mt-3 px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-sm font-medium transition-colors">
                      Analyze Match
                    </button>
                  </div>
                </div>
              ))}
              
              {futureMatches.length === 0 && (
                <div className="text-center p-12 bg-gray-900 border border-gray-800 rounded-xl text-slate-400">
                  No upcoming fixtures found. Run data sync pipeline.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
