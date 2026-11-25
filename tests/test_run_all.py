"""Checks for the single-command laptop inference launcher."""

import socket
import tempfile
import unittest
from queue import Queue
from pathlib import Path
from unittest.mock import Mock, patch

import run_all


class LauncherTests(unittest.TestCase):
    def test_artifact_checkout_requires_python_models_and_processed_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            python = root / "env" / "Scripts" / "python.exe"
            python.parent.mkdir(parents=True)
            python.touch()
            (root / "model_artifacts").mkdir()
            with self.assertRaises(run_all.StartupError):
                run_all.find_artifacts(root)
            (root / "data" / "processed").mkdir(parents=True)
            with self.assertRaises(run_all.StartupError):
                run_all.find_artifacts(root)
            for name in ("ProductUI_Model", "ProductUI_Model_meta.pkl", "tribe_odi.pkl", "tribe_test.pkl"):
                (root / "model_artifacts" / name).touch()
            resolved = root.resolve()
            self.assertEqual(run_all.find_artifacts(root),
                             (resolved, resolved / "env" / "Scripts" / "python.exe"))

    def test_only_accepted_tunnel_urls_are_reported(self):
        self.assertEqual(
            run_all.tunnel_url("Visit https://developers.cloudflare.com then https://abc.trycloudflare.com"),
            "https://abc.trycloudflare.com",
        )
        self.assertEqual(run_all.tunnel_url("Forwarding HTTPS: https://demo.lhr.life."),
                         "https://demo.lhr.life")
        self.assertIsNone(run_all.tunnel_url('Post "https://api.trycloudflare.com/tunnel": DNS failed'))
        self.assertIsNone(run_all.tunnel_url("https://example.invalid"))

    def test_invalid_website_origins_rejected(self):
        for value in ("http://new-x1.pages.dev", "https://new-x1.pages.dev/account",
                      "https://name:secret@new-x1.pages.dev", "https://new-x1.pages.dev/?x=1"):
            with self.subTest(value=value), self.assertRaises(run_all.StartupError):
                run_all.validate_origin(value)

    def test_missing_format_blocks_ready_message(self):
        process = Mock()
        process.poll.return_value = None
        with patch.object(run_all, "get_health", return_value={"models": {"t20": True, "odi": False, "test": True}}):
            with self.assertRaisesRegex(run_all.StartupError, "odi"):
                run_all.wait_for_api(process, 8001)

    def test_public_url_waits_for_healthy_tunnel(self):
        process = Mock()
        process.poll.return_value = None
        tunnel = run_all.Tunnel(process, Queue(), "cloudflare", "https://demo.trycloudflare.com")
        ready = {"status": "ok", "models": {name: True for name in run_all.MODEL_FORMATS}}
        with patch.object(run_all, "get_health", side_effect=[OSError("HTTP 530"), ready]) as check:
            with patch.object(run_all.time, "sleep"):
                self.assertEqual(run_all.wait_for_public_api(tunnel), ready)
        self.assertEqual(check.call_count, 2)
        self.assertEqual(check.call_args.args[0], tunnel.url + "/health")

    def test_public_url_accepts_degraded_data_when_models_are_ready(self):
        # A stale fixture feed reports "degraded"; the models still serve, so the tunnel goes online.
        process = Mock()
        process.poll.return_value = None
        tunnel = run_all.Tunnel(process, Queue(), "cloudflare", "https://demo.trycloudflare.com")
        degraded = {"status": "degraded", "models": {name: True for name in run_all.MODEL_FORMATS}}
        with patch.object(run_all, "get_health", return_value=degraded), patch.object(run_all.time, "sleep"):
            self.assertEqual(run_all.wait_for_public_api(tunnel), degraded)

    def test_public_url_rejects_missing_models_with_the_real_reason(self):
        process = Mock()
        process.poll.return_value = None
        lines = Queue()
        lines.put("INF precheck component=\"UDP Connectivity\" details=\"QUIC connection failed\"")
        tunnel = run_all.Tunnel(process, lines, "cloudflare", "https://demo.trycloudflare.com")
        partial = {"status": "ok", "models": {"t20": True, "odi": False, "test": True}}
        with patch.object(run_all, "get_health", return_value=partial), patch.object(run_all.time, "sleep"), \
             patch.object(run_all.time, "monotonic", side_effect=[0, 0, 1000]):
            with self.assertRaisesRegex(run_all.StartupError, "three models"):
                run_all.wait_for_public_api(tunnel)

    def test_occupied_port_is_not_reused(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            with self.assertRaisesRegex(run_all.StartupError, "already in use"):
                run_all.check_port(listener.getsockname()[1])


if __name__ == "__main__":
    unittest.main()
