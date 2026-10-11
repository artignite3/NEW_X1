"""Timeout, isolation, quota and failure-publication checks without provider calls."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from pipeline.runtime import exclusive_lock
from run_daily_sync import run_stage, run_sync
from data.future_matches import squad_fetcher


class PipelineTests(unittest.TestCase):
    def test_stage_has_timeout_and_redacts_secrets(self):
        result = subprocess.CompletedProcess([], 1, "secret-value", "failed")
        with patch("run_daily_sync.subprocess.run", return_value=result) as run:
            outcome = run_stage("fixed.module", timeout=12, attempts=2, environment={"API_KEY": "secret-value"})
        self.assertEqual(outcome["status"], "failed")
        self.assertNotIn("secret-value", outcome["output"])
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args.kwargs["timeout"], 12)

    def test_timeout_is_a_failed_stage(self):
        with patch("run_daily_sync.subprocess.run", side_effect=subprocess.TimeoutExpired("fixed", 1)):
            self.assertEqual(run_stage("fixed", timeout=1)["status"], "failed")

    def test_failed_ingestion_stops_features_and_persists_run_failure(self):
        with tempfile.TemporaryDirectory() as folder, patch("run_daily_sync.run_stage", return_value={"name": "ingest", "status": "failed", "seconds": 1}) as stage:
            report = run_sync(skip_download=True, environment={"APP_ENV": "test", "NEW_X1_DATA_ROOT": folder})
            self.assertEqual(report["status"], "failed")
            self.assertEqual(stage.call_count, 1)
            self.assertEqual(json.loads((Path(folder) / "pipeline_status.json").read_text())["status"], "failed")

    def test_full_sync_includes_schedule_and_quota_bounded_squads(self):
        def outcome(module, *args, **kwargs):
            return {"name": module, "status": "degraded" if module.endswith("squad_fetcher") else "ok", "seconds": 0}
        with tempfile.TemporaryDirectory() as folder, patch("run_daily_sync.run_stage", side_effect=outcome) as stage:
            report = run_sync(environment={"APP_ENV": "test", "NEW_X1_DATA_ROOT": folder, "SQUAD_REQUEST_BUDGET": "3"})
            self.assertEqual(report["status"], "degraded")
            names = [call.args[0] for call in stage.call_args_list]
            self.assertIn("data.future_matches.schedule_fetcher", names)
            self.assertIn("data.future_matches.squad_fetcher", names)
        self.assertEqual(stage.call_args_list[-1].args[1], ("--max-requests", "3"))

    def test_production_sync_cannot_mutate_serving_directory_directly(self):
        with self.assertRaises(ValueError): run_sync(environment={"APP_ENV": "production"})

    def test_overlap_lock_is_released_even_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            lock = Path(folder) / "pipeline.lock"
            with exclusive_lock(lock):
                with self.assertRaises(OSError):
                    with exclusive_lock(lock): pass
            with exclusive_lock(lock): pass

    def test_squad_provider_budget_bounds_actual_requests(self):
        with patch.object(squad_fetcher, "_REQUESTS", 0), patch.object(squad_fetcher, "_MAX_REQUESTS", 1), \
             patch.dict(os.environ, {"RAPID_API_KEY": "test-key"}), patch("data.future_matches.squad_fetcher.requests.get") as request:
            request.return_value.json.return_value = {"squads": []}
            squad_fetcher.fetch("fixed")
            with self.assertRaises(squad_fetcher.RequestBudgetExceeded): squad_fetcher.fetch("other")
            self.assertEqual(request.call_count, 1)

    def test_empty_squad_response_cannot_replace_existing_entry(self):
        existing = {"available_squads": [{"team_name": "Alpha", "players": [{"player_name": "Known"}]}]}
        original = deepcopy(existing)
        match = {"series_id": 1, "match_id": 1, "team1": "Alpha", "team2": "Beta", "match_type": "T20"}
        with patch.object(squad_fetcher, "get_series_squads", return_value={"squads": []}):
            self.assertIsNone(squad_fetcher.refresh_match(match, existing))
        self.assertEqual(existing, original)


if __name__ == "__main__": unittest.main()
