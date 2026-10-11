"""Run the NEW_X1 inference API and a temporary tunnel for the Pages site.

FastAPI loads all three ML formats in its own process. The website is already
hosted on Cloudflare Pages, so no local Next.js or Streamlit server is needed.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SITE = "https://new-x1.pages.dev"
MODEL_FORMATS = ("t20", "odi", "test")
TUNNEL_URL = re.compile(r"https://[a-zA-Z0-9.-]+")
TUNNEL_HOST_SUFFIXES = (".trycloudflare.com", ".lhr.life", ".localhost.run")


class StartupError(RuntimeError):
    """A required local service or artifact is unavailable."""


def validate_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise StartupError("--site-origin must be an HTTPS origin without a path or credentials")
    return value.rstrip("/")


def artifact_python(root: Path) -> Path | None:
    paths = (root / "env" / "Scripts" / "python.exe", root / "env" / "bin" / "python")
    return next((path for path in paths if path.is_file()), None)


def has_all_models(root: Path) -> bool:
    models = root / "model_artifacts"
    names = ("ProductUI_Model", "ProductUI_Model_meta.pkl", "tribe_odi.pkl", "tribe_test.pkl")
    return all((models / name).exists() or (models / (name + ".last_good")).exists()
               for name in names)


def find_artifacts(explicit: Path | None) -> tuple[Path, Path]:
    candidates = [explicit] if explicit else [
        Path(os.environ["NEW_X1_ARTIFACTS_ROOT"]) if os.environ.get("NEW_X1_ARTIFACTS_ROOT") else None,
        PROJECT_ROOT,
        PROJECT_ROOT.parent / "NEW_X1",
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        root = candidate.expanduser().resolve()
        python = artifact_python(root)
        if python and has_all_models(root) and (root / "data" / "processed").is_dir():
            return root, python
    raise StartupError(
        "Could not find the artifact checkout (env, all three model formats, data/processed). "
        "Pass --artifacts-root with its absolute path."
    )


def tunnel_url(line: str) -> str | None:
    for match in TUNNEL_URL.finditer(line):
        value = match.group(0).rstrip(".,;)]}")
        host = urlsplit(value).hostname or ""
        if host != "api.trycloudflare.com" and host.endswith(TUNNEL_HOST_SUFFIXES):
            return value
    return None


def get_health(url: str, timeout: float = 3) -> dict:
    with urlopen(url, timeout=timeout) as response:
        if response.status != 200:
            raise StartupError(f"Health check returned HTTP {response.status}")
        return json.load(response)


def wait_for_api(process: subprocess.Popen, port: int, timeout: int = 90) -> dict:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/health"
    while time.monotonic() < deadline:
        code = process.poll()
        if code is not None:
            raise StartupError(f"API exited during startup (code {code})")
        try:
            health = get_health(url)
            missing = [name for name in MODEL_FORMATS if not health.get("models", {}).get(name)]
            if missing:
                raise StartupError("API started, but ML models are unavailable: " + ", ".join(missing))
            return health
        except (OSError, ValueError, TimeoutError):
            time.sleep(1)
    raise StartupError(f"API was not healthy after {timeout} seconds: {url}")


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def cloudflared_command(port: int) -> list[str]:
    installed = shutil.which("cloudflared")
    windows_default = Path(r"C:\Program Files (x86)\cloudflared\cloudflared.exe")
    binary = installed or (str(windows_default) if windows_default.is_file() else None)
    if not binary:
        raise StartupError("cloudflared is not installed or on PATH")
    return [binary, "tunnel", "--url", f"http://127.0.0.1:{port}"]


def localhost_run_command(port: int) -> list[str]:
    ssh = shutil.which("ssh")
    if not ssh:
        raise StartupError("OpenSSH is not installed or on PATH")
    return [ssh, "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=accept-new", "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=30", "-R", f"80:127.0.0.1:{port}",
            "nokey@localhost.run"]


@dataclass
class Tunnel:
    process: subprocess.Popen
    lines: queue.Queue[str]
    provider: str
    url: str


def launch_tunnel(provider: str, port: int, timeout: int = 30) -> Tunnel:
    command = cloudflared_command(port) if provider == "cloudflare" else localhost_run_command(port)
    process = subprocess.Popen(command, cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace", bufsize=1)
    lines: queue.Queue[str] = queue.Queue()

    def read_output() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            lines.put(line.rstrip())

    threading.Thread(target=read_output, daemon=True).start()
    deadline = time.monotonic() + timeout
    recent: list[str] = []
    while time.monotonic() < deadline:
        try:
            line = lines.get(timeout=0.25)
            recent.append(line)
            url = tunnel_url(line)
            if url:
                return Tunnel(process, lines, provider, url)
        except queue.Empty:
            pass
        if process.poll() is not None and lines.empty():
            break
    stop_process(process)
    detail = next((line for line in reversed(recent)
                   if any(word in line.lower() for word in ("failed", "error", "could not"))),
                  recent[-1] if recent else "no URL received")
    detail = detail[-500:]
    raise StartupError(f"{provider} tunnel unavailable: {detail}")


def check_port(port: int) -> None:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            raise StartupError(f"Port {port} is already in use; stop the existing API first")
    except OSError:
        return


def start_api(python: Path, artifacts: Path, origin: str, port: int) -> subprocess.Popen:
    environment = os.environ.copy()
    environment.update({
        "APP_ENV": "staging",
        "CORS_ORIGINS": f"{origin},http://localhost:3000,http://127.0.0.1:3000",
        "NEW_X1_DATA_ROOT": str(artifacts / "data"),
        "NEW_X1_MODEL_ROOT": str(artifacts / "model_artifacts"),
    })
    command = [str(python), "-m", "uvicorn", "model.model_fastapi:app",
               "--host", "127.0.0.1", "--port", str(port)]
    env_file = artifacts / ".env"
    if env_file.is_file():
        command.extend(("--env-file", str(env_file)))
    return subprocess.Popen(command, cwd=PROJECT_ROOT, env=environment)


def options() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-root", type=Path, help="checkout containing env, data and model_artifacts")
    parser.add_argument("--site-origin", default=DEFAULT_SITE)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--tunnel", choices=("auto", "cloudflare", "localhost-run"), default="auto")
    parser.add_argument("--local-only", action="store_true", help="run API without a public tunnel")
    parser.add_argument("--retry-seconds", type=int, default=60, help="wait before retrying failed tunnels")
    return parser.parse_args()


def main() -> int:
    args = options()
    api: subprocess.Popen | None = None
    tunnel: Tunnel | None = None
    try:
        if not 1 <= args.port <= 65535 or args.retry_seconds < 1:
            raise StartupError("--port must be 1-65535 and --retry-seconds must be positive")
        origin = validate_origin(args.site_origin)
        artifacts, python = find_artifacts(args.artifacts_root)
        check_port(args.port)
        print(f"Website: {origin} (already hosted on Cloudflare Pages)", flush=True)
        print(f"Models and data: {artifacts}", flush=True)
        print(f"Starting inference API: http://127.0.0.1:{args.port}", flush=True)
        api = start_api(python, artifacts, origin, args.port)
        health = wait_for_api(api, args.port)
        print("ML ready: " + ", ".join(MODEL_FORMATS) + f"; health={health['status']}", flush=True)
        for feed in ("fixtures", "squads"):
            warning = health.get(feed, {}).get("warning")
            if warning:
                print(f"{feed} warning: {warning}", flush=True)
        if args.local_only:
            print("Local-only mode: the Cloudflare website cannot use this API yet.", flush=True)
        providers = ("cloudflare", "localhost-run") if args.tunnel == "auto" else (args.tunnel,)
        next_retry = 0.0
        while True:
            if api.poll() is not None:
                raise StartupError(f"API stopped unexpectedly (code {api.returncode})")
            if not args.local_only and tunnel and tunnel.process.poll() is not None:
                print("Tunnel disconnected; retrying shortly.", flush=True)
                stop_process(tunnel.process)
                tunnel = None
                next_retry = 0.0
            if not args.local_only and tunnel is None and time.monotonic() >= next_retry:
                for provider in providers:
                    try:
                        print(f"Connecting {provider} tunnel...", flush=True)
                        tunnel = launch_tunnel(provider, args.port)
                        print(f"PUBLIC API: {tunnel.url}", flush=True)
                        print(f"Open {origin}/settings and paste this URL, then Save and test connection.", flush=True)
                        try:
                            public_health = get_health(tunnel.url + "/health", timeout=8)
                            print(f"Public API check: {public_health.get('status', 'unknown')}", flush=True)
                        except (OSError, ValueError, TimeoutError) as exc:
                            print(f"Public API check could not complete: {exc}", flush=True)
                        break
                    except StartupError as exc:
                        print(exc, flush=True)
                if tunnel is None:
                    print(f"API remains local; retrying tunnels in {args.retry_seconds}s.", flush=True)
                    next_retry = time.monotonic() + args.retry_seconds
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping NEW_X1...", flush=True)
        return 0
    except (OSError, StartupError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        stop_process(tunnel.process if tunnel else None)
        stop_process(api)


if __name__ == "__main__":
    raise SystemExit(main())
