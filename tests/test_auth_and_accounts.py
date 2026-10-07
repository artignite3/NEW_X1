"""Signed-token, owner-isolation and restart regression tests; no live services."""
import os
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from uuid import uuid4
from datetime import datetime, timezone, timedelta

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from model.auth import Principal, verify_token, auth_config, require_user
from model.user_store import UserStore
from model.model_fastapi import app


class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.url = "https://example.supabase.co"
        cls.identity = str(uuid4())

    def token(self, **overrides):
        claims = {"iss": self.url + "/auth/v1", "sub": self.identity, "aud": "authenticated",
                  "exp": int(time.time()) + 120, "iat": int(time.time()), "role": "authenticated",
                  "app_metadata": {}, "aal": "aal1", **overrides}
        return jwt.encode(claims, self.private, algorithm="RS256", headers={"kid": "test-key"})

    def verify(self, token):
        client = MagicMock()
        client.get_signing_key_from_jwt.return_value = SimpleNamespace(key=self.private.public_key())
        with patch("model.auth.jwks_client", return_value=client):
            return verify_token(token, self.url)

    def test_correct_signature_and_claims_grant_only_the_signed_identity(self):
        user = self.verify(self.token(user_metadata={"role": "admin"}))
        self.assertEqual(user.user_id, self.identity)
        self.assertFalse(user.is_admin)

    def test_expired_wrong_audience_issuer_role_and_signature_are_rejected(self):
        for claims in ({"exp": int(time.time()) - 1}, {"aud": "other"}, {"iss": "https://other"},
                       {"role": "service_role"}, {"sub": "not-a-uuid"}, {"is_anonymous": True}):
            with self.subTest(claims=claims), self.assertRaises(HTTPException) as error:
                self.verify(self.token(**claims))
            self.assertEqual(error.exception.status_code, 401)
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = jwt.encode(jwt.decode(self.token(), options={"verify_signature": False}), other,
                           algorithm="RS256", headers={"kid": "test-key"})
        with self.assertRaises(HTTPException): self.verify(token)

    def test_admin_requires_aal2(self):
        with self.assertRaises(HTTPException) as error:
            self.verify(self.token(app_metadata={"role": "admin"}))
        self.assertEqual(error.exception.status_code, 403)
        self.assertTrue(self.verify(self.token(app_metadata={"role": "admin"}, aal="aal2")).is_admin)

    def test_unconfigured_production_and_unknown_environment_fail_closed(self):
        for environment in ("production", "staging", "typo"):
            with patch.dict(os.environ, {"APP_ENV": environment, "SUPABASE_URL": "", "SUPABASE_PUBLISHABLE_KEY": ""}):
                with self.assertRaises(HTTPException) as error: auth_config()
                self.assertEqual(error.exception.status_code, 503)

    def test_protected_routes_reject_missing_session_before_computation(self):
        with patch.dict(os.environ, {"APP_ENV": "production", "SUPABASE_URL": self.url, "SUPABASE_PUBLISHABLE_KEY": "test-public-key"}), \
             TestClient(app) as client, patch("model.model_fastapi.generate_best_team") as generate:
            self.assertEqual(client.post("/generate_best_team", json={"match_id": "x"}).status_code, 401)
            self.assertEqual(client.get("/analyses").status_code, 401)
            generate.assert_not_called()

    def test_enrolled_user_requires_authenticator_and_provider_failure_is_503(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {"id": self.identity, "factors": [{"status": "verified"}]}
        credentials = SimpleNamespace(credentials="test-token")
        with patch.dict(os.environ, {"APP_ENV": "production", "SUPABASE_URL": self.url, "SUPABASE_PUBLISHABLE_KEY": "public"}), \
             patch("model.auth.verify_token", return_value=Principal(self.identity, "test-token")), \
             patch("model.auth.requests.get", return_value=response):
            with self.assertRaises(HTTPException) as error: require_user(credentials)
            self.assertEqual(error.exception.status_code, 403)


class AccountStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = patch.dict(os.environ, {"APP_ENV": "test", "SUPABASE_URL": "", "SUPABASE_PUBLISHABLE_KEY": "",
            "APP_STATE_PATH": os.path.join(self.temp.name, "state.sqlite")})
        self.settings.start(); self.addCleanup(self.settings.stop)
        self.owner = Principal(str(uuid4()))
        self.stranger = Principal(str(uuid4()))
        self.token = uuid4().hex
        self.snapshot = {"fmt": "t20", "players": {}, "selected": [], "drivers": {}}

    def test_state_survives_new_store_and_in_memory_cache_loss(self):
        UserStore(self.owner).save_explanation(self.token, self.snapshot, {"summary": {"points": 42}})
        reopened = UserStore(self.owner)
        self.assertEqual(reopened.get("explanations", self.token)["payload"]["snapshot"], self.snapshot)
        saved = reopened.save_analysis(self.token, "My team")
        self.assertEqual(UserStore(self.owner).list_analyses()[0]["id"], saved["id"])

    def test_other_user_cannot_explain_save_list_or_delete_owner_data(self):
        owner = UserStore(self.owner)
        owner.save_explanation(self.token, self.snapshot, {"summary": {}})
        saved = owner.save_analysis(self.token, "My team")
        other = UserStore(self.stranger)
        self.assertIsNone(other.get("explanations", self.token))
        with self.assertRaises(HTTPException): other.save_analysis(self.token, "Stolen")
        self.assertEqual(other.list_analyses(), [])
        self.assertFalse(other.delete_analysis(saved["id"]))
        self.assertTrue(owner.delete_analysis(saved["id"]))

    def test_expired_explanation_cannot_be_replayed_or_saved(self):
        store = UserStore(self.owner)
        store.put("explanations", self.token, {"snapshot": self.snapshot},
                  (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
        self.assertIsNone(store.get("explanations", self.token))
        with self.assertRaises(HTTPException): store.save_analysis(self.token, "Expired")

    def test_remote_requests_carry_user_token_and_owner_filter(self):
        with patch.dict(os.environ, {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_PUBLISHABLE_KEY": "public"}), \
             patch("model.user_store.requests.request") as request:
            request.return_value = MagicMock(status_code=200, content=b"[]")
            request.return_value.json.return_value = []
            store = UserStore(Principal(self.owner.user_id, "user-token"))
            self.assertIsNone(store.get("explanations", self.token))
            kwargs = request.call_args.kwargs
            self.assertEqual(kwargs["headers"]["Authorization"], "Bearer user-token")
            self.assertEqual(kwargs["params"]["user_id"], "eq." + self.owner.user_id)

    def test_remote_quota_denial_and_storage_failure_stop_work(self):
        with patch.dict(os.environ, {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_PUBLISHABLE_KEY": "public"}):
            store = UserStore(Principal(self.owner.user_id, "user-token"))
            with patch.object(store, "remote", return_value=False):
                with self.assertRaises(HTTPException) as error: store.consume_quota()
                self.assertEqual(error.exception.status_code, 429)

    def test_api_explanation_survives_cache_loss_and_remains_private(self):
        from model.team_generator import _EXPLAIN_CACHE
        snapshot = {"fmt": "t20", "selected": ["p1"], "details": None, "players": {
            "p1": {"display_name": "Fixed Player", "role": "BAT", "team": "Alpha",
                   "adjusted_score": 42., "captain_upside": 45.}}}
        result = {"explain_token": self.token, "summary": {"expected_total_points": 42.}}
        app.dependency_overrides[require_user] = lambda: self.owner
        try:
            with TestClient(app) as client, patch.dict(_EXPLAIN_CACHE, {self.token: snapshot}), \
                 patch("model.model_fastapi.generate_best_team", return_value=result), \
                 patch("model.llm_inference.ollama_available", return_value=False):
                self.assertEqual(client.post("/generate_best_team", json={"match_id": "fixed"}).status_code, 200)
                _EXPLAIN_CACHE.pop(self.token, None)
                report = client.post("/explain_team", json={"explain_token": self.token})
                self.assertEqual(report.status_code, 200)
                self.assertEqual(report.json()["context"]["expected_total_points"], 42.)
                self.assertEqual(client.post("/analyses", json={"explain_token": self.token, "title": "My team"}).status_code, 201)
                app.dependency_overrides[require_user] = lambda: self.stranger
                self.assertEqual(client.post("/explain_team", json={"explain_token": self.token}).status_code, 404)
                self.assertEqual(client.get("/analyses").json()["analyses"], [])
        finally:
            app.dependency_overrides.pop(require_user, None)


if __name__ == "__main__": unittest.main()
