# Website components

`FixturesBoard.tsx` labels fixture/squad availability; `AnalysisResult.tsx`, `PlayerCard.tsx` and `IntelligencePanels.tsx` render recommendation evidence. `AccountPanel.tsx` provides account controls, and `AppNav.tsx` displays navigation and API availability. `StatusBadge.tsx`, `RoleBadge.tsx`, `icons.tsx` and `ui.tsx` are shared visual primitives.

Components consume typed data from [`lib/`](../lib/README.md) and are used by [`app/`](../app/README.md). They require an API for live analysis and Supabase for configured login. Run frontend lint and static build from [`frontend`](../../README.md); the Python contract suite covers backend behavior separately.
