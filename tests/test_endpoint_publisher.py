"""The launcher publishes its tunnel address only when configured, and never leaks the token in the URL."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_all

TOKEN = "t" * 48
SETTINGS = {"SUPABASE_URL": "https://demo.supabase.co/", "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_x",
            "NEW_X1_PUBLISH_TOKEN": TOKEN}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class EndpointPublisherTest(unittest.TestCase):
    def test_disabled_without_complete_settings(self):
        for missing in SETTINGS:
            publisher = run_all.EndpointPublisher({k: v for k, v in SETTINGS.items() if k != missing})
            self.assertFalse(publisher.enabled)
            self.assertFalse(publisher.publish("https://a-b.trycloudflare.com"))
        self.assertFalse(run_all.EndpointPublisher({**SETTINGS, "NEW_X1_PUBLISH_TOKEN": "short"}).enabled)

    def test_publishes_address_and_clears_it(self):
        publisher = run_all.EndpointPublisher(SETTINGS)
        with patch.object(run_all, "urlopen", side_effect=lambda *a, **k: FakeResponse(b"true")) as call:
            self.assertTrue(publisher.publish("https://a-b.trycloudflare.com"))
            self.assertTrue(publisher.published)
            request = call.call_args.args[0]
            self.assertEqual(request.full_url, "https://demo.supabase.co/rest/v1/rpc/publish_backend_endpoint")
            self.assertNotIn(TOKEN, request.full_url)
            self.assertEqual(json.loads(request.data), {"p_url": "https://a-b.trycloudflare.com", "p_token": TOKEN})
            self.assertEqual(request.get_header("Apikey"), "sb_publishable_x")
            self.assertTrue(publisher.publish(None))
            self.assertFalse(publisher.published)

    def test_rejected_token_or_network_error_is_not_published(self):
        publisher = run_all.EndpointPublisher(SETTINGS)
        with patch.object(run_all, "urlopen", return_value=FakeResponse(b"false")):
            self.assertFalse(publisher.publish("https://a-b.trycloudflare.com"))
        with patch.object(run_all, "urlopen", side_effect=OSError("offline")):
            self.assertFalse(publisher.publish("https://a-b.trycloudflare.com"))
        self.assertFalse(publisher.published)

    def test_env_file_reader(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text("# comment\nA=1\nB = \"two\"\nbad line\nC='3'\n", encoding="utf-8")
            self.assertEqual(run_all.read_env_file(path), {"A": "1", "B": "two", "C": "3"})
            self.assertEqual(run_all.read_env_file(Path(folder) / "missing"), {})


if __name__ == "__main__":
    unittest.main()
