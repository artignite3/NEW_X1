# Pitch Control report

## Goal and current status

Show a defensible venue-history report when a verified match-day pitch assessment is unavailable. The report is historical evidence, not a claim about the exact strip or weather on match day. The descriptive report, offline snapshot, last-good recovery, API response, and simulator panel are implemented on `codex/pitch-control-report`. Historical evidence does not yet alter fantasy-point multipliers; that requires the independent backtest below.

## Source and identity

The offline builder reads Cricsheet JSON archives and, when present, the project's derived bowling-style CSVs. It skips records with missing ball data, unusual outcome methods, super overs, and incomplete first innings. The checked-in compact snapshot lets the API serve without the large raw archives. A pipeline stage refreshes it after ingestion; the publication process checks its checksum and retains the previous valid version. If derived style CSVs are absent in a hosted refresh, previously validated style aggregates are reused for existing matches, while new style evidence remains unknown.

The currently available local archives do not have Cricsheet venue registry IDs. Name matching is deliberately exact after normalization and reviewed aliases. A name used in multiple cities requires the city in the fixture. New aliases must be reviewed against source records before adding them.

## Report rules

1. Use only matches completed before the requested date, of the requested gender, within five years. A multi-day Test becomes available after its final day. Ignore a venue whose latest qualifying match is over three years old.
2. Take the latest ten matches and display both last-five and last-ten windows. Raw first-innings averages, runs per over, and boundaries only combine matches of the requested format. When no same-format match exists, show no raw average. Show defended games and below-peer totals defended as supporting evidence, never as proof of pitch cause.
3. Compare each match's scoring and wicket rate with its own contemporaneous format, gender, and team-level peers. At least twenty prior peers are required per match. A minimum of five qualified venue matches is required for a report. Ten qualified matches yield moderate confidence; otherwise confidence is low.
4. Label scoring as batting-friendly when mean adjusted scoring is at least 10% above peers and the latest five are at least 5% above; label bowling-friendly at the symmetric low thresholds. Otherwise label balanced. These are provisional descriptive thresholds, not validated predictive effects.
5. Compare spin and pace bowling within format and innings phase. Require at least 120 legal balls for each style. If styles cannot be joined reliably, report insufficient evidence. This is historical bowling-style performance, not direct observation of today's surface.

## Fallback order

Use a verified match-specific report when one is integrated in the future. Otherwise use qualified history, the existing curated T20 prior, or neutral multipliers. Snapshot load tries current, last-good, then the packaged snapshot. Invalid files are rejected. Expose source, evidence count, date window, confidence, and backup status in the API and UI.

## Remaining gate before historical score adjustments

Run rolling-date backtests where each simulated fixture sees only earlier matches. Measure classification stability, venue coverage, calibration of confidence, and recommendation regret versus neutral and existing curated prior. Stratify by format, gender, team level, sample count, and style coverage. Tune thresholds on a development period and confirm on untouched later matches. Only if the holdout improves should capped score multipliers be added behind a flag. Do not imply a prediction improvement from the descriptive report alone.

## Operational checks

Run the venue unit tests, pipeline and release tests, frontend type/lint/build checks, and a real generation request for a covered and an uncovered venue. Inspect the published UI after deployment. Attribute Cricsheet-derived data and retain the source licence link.
