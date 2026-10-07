"""Validate and publish fixture feeds with an auditable last-good fallback."""
from __future__ import annotations

import json
import os
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIMARY = HERE / "upcoming_matches.json"
BACKUP = HERE / "upcoming_matches.last_good.json"
VALID_FORMATS = {"T20", "ODI", "TEST"}


def validate_feed(payload: dict) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("matches"), list):
        raise ValueError("Fixture feed must contain a matches array")
    if not payload.get("fetched_at") or not payload.get("source"):
        raise ValueError("Fixture feed requires fetched_at and source")
    datetime.fromisoformat(payload["fetched_at"].replace("Z", "+00:00"))
    ids = set()
    for match in payload["matches"]:
        if not isinstance(match, dict):
            raise ValueError("Fixture entry is not an object")
        identity = str(match.get("match_id", "")).strip()
        if not identity or identity in ids:
            raise ValueError("Fixture IDs must be present and unique")
        ids.add(identity)
        if not all(isinstance(match.get(k), str) and match[k].strip() for k in ("team1", "team2", "date")):
            raise ValueError(f"Fixture {identity} has incomplete teams or date")
        date.fromisoformat(match["date"])
        if match["team1"].casefold() == match["team2"].casefold():
            raise ValueError(f"Fixture {identity} has identical teams")
        if str(match.get("match_type", "")).upper() not in VALID_FORMATS:
            raise ValueError(f"Fixture {identity} has unsupported format")
    return payload


def read_valid(path: Path) -> dict:
    return validate_feed(json.loads(path.read_text(encoding="utf-8")))


def publish(payload: dict, primary: Path = PRIMARY, backup: Path = BACKUP) -> None:
    """Keep the old valid feed before atomically making a new one visible."""
    validate_feed(payload)
    primary.parent.mkdir(parents=True, exist_ok=True)
    if primary.exists():
        try:
            previous = read_valid(primary)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        else:
            still_future = any(date.fromisoformat(m["date"]) > date.today() and not m.get("match_ended")
                               for m in previous["matches"])
            if still_future and not payload["matches"]:
                raise ValueError("Refusing to erase future fixtures with an empty refresh")
            backup_tmp = backup.with_suffix(backup.suffix + ".tmp")
            shutil.copyfile(primary, backup_tmp)
            os.replace(backup_tmp, backup)
    temporary = primary.with_suffix(primary.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, primary)


def load(primary: Path = PRIMARY, backup: Path = BACKUP, today: date | None = None) -> dict:
    """Only verified, future records are served; provenance reveals fallback."""
    today = today or date.today()
    failures = []
    for path, fallback in ((primary, False), (backup, True)):
        try:
            payload = read_valid(path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            failures.append(f"{path.name}: {type(error).__name__}")
            continue
        matches = [m for m in payload["matches"] if date.fromisoformat(m["date"]) > today and not m.get("match_ended")]
        fetched = datetime.fromisoformat(payload["fetched_at"].replace("Z", "+00:00"))
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        stale = datetime.now(timezone.utc) - fetched.astimezone(timezone.utc) > timedelta(hours=24)
        warnings = failures + (["Fixture feed last fetched over 24 hours ago"] if stale else [])
        return {"matches": matches, "source": payload["source"], "fetched_at": payload["fetched_at"],
                "fallback_used": fallback, "warning": "; ".join(warnings) if warnings else None}
    return {"matches": [], "source": None, "fetched_at": None, "fallback_used": False,
            "warning": "No valid fixture feed: " + "; ".join(failures)}
