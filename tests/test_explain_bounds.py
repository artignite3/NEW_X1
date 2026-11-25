"""Explanation snapshots are user-writable rows, so the API must bound the work they request."""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from model.auth import Principal, require_user
from model.model_fastapi import _valid_snapshot, app


def snapshot(selected, players=None):
    players = players if players is not None else {key: {"display_name": key} for key in selected}
    return {"fmt": "t20", "selected": selected, "players": players, "drivers": {}}


class ExplainBoundsTest(unittest.TestCase):
    def test_accepts_a_normal_eleven(self):
        self.assertTrue(_valid_snapshot(snapshot([f"p{i}" for i in range(11)])))

    def test_rejects_oversized_or_malformed_snapshots(self):
        self.assertFalse(_valid_snapshot(snapshot([f"p{i}" for i in range(500)])))
        self.assertFalse(_valid_snapshot(snapshot([])))
        self.assertFalse(_valid_snapshot(snapshot(["p1"], players={})))
        self.assertFalse(_valid_snapshot(snapshot(["p1"], players={f"p{i}": {} for i in range(1000)})))
        self.assertFalse(_valid_snapshot({"selected": "p1", "players": {}}))
        self.assertFalse(_valid_snapshot(None))

    def test_api_refuses_a_crafted_snapshot_before_any_model_call(self):
        token = "a" * 32
        crafted = {"id": token, "payload": {"snapshot": snapshot([f"p{i}" for i in range(500)])}}
        app.dependency_overrides[require_user] = lambda: Principal("00000000-0000-0000-0000-000000000002", "test-token")
        try:
            with TestClient(app) as client, patch("model.user_store.UserStore.get", return_value=crafted), \
                 patch("intelligence.llm_analyst.generate_team_report") as report:
                response = client.post("/explain_team", json={"explain_token": token})
            self.assertEqual(response.status_code, 400)
            report.assert_not_called()
        finally:
            app.dependency_overrides.pop(require_user, None)

    def test_match_squads_requires_sign_in(self):
        with patch.dict("os.environ", {"APP_ENV": "production", "SUPABASE_URL": "https://test.supabase.co",
                                       "SUPABASE_PUBLISHABLE_KEY": "public"}), TestClient(app) as client:
            self.assertEqual(client.get("/match_squads", params={"match_id": "1"}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
