"""Verified, atomic squad snapshots. An unavailable feed never invents players."""
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from project_paths import data_root
PRIMARY = data_root() / "future_matches" / "upcoming_squads.json"
BACKUP = PRIMARY.with_name("upcoming_squads.last_good.json")


def validate(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("squads"), dict):
        raise ValueError("Squad feed must contain a squads object")
    datetime.fromisoformat(str(payload.get("fetched_at", "")).replace("Z", "+00:00"))
    for key, entry in payload["squads"].items():
        if not str(key).strip() or not isinstance(entry, dict):
            raise ValueError("Invalid squad entry")
        blocks = entry.get("available_squads")
        if blocks is not None:
            if not isinstance(blocks, list):
                raise ValueError("Squad blocks must be a list")
            for block in blocks:
                if not isinstance(block, dict) or not isinstance(block.get("players"), list):
                    raise ValueError("Invalid squad block")
    return payload


def read_valid(path):
    return validate(json.loads(Path(path).read_text(encoding="utf-8")))


def publish(payload, primary=None, backup=None):
    primary, backup = Path(primary or PRIMARY), Path(backup or BACKUP)
    primary.parent.mkdir(parents=True, exist_ok=True)
    validate(payload)
    previous = None
    if primary.exists():
        try:
            previous = read_valid(primary)
        except (OSError, ValueError, TypeError):
            pass
    if previous is None and backup.exists():
        try:
            previous = read_valid(backup)
        except (OSError, ValueError, TypeError):
            pass
    if previous is not None:
        if previous["squads"] and not payload["squads"]:
            raise ValueError("Refusing to replace a nonempty squad feed with an empty one")
    if primary.exists() and previous is not None:
        try:
            read_valid(primary)
        except (OSError, ValueError, TypeError):
            pass
        else:
            temp_backup = backup.with_name(backup.name + ".tmp")
            shutil.copyfile(primary, temp_backup)
            os.replace(temp_backup, backup)
    temp = primary.with_name(primary.name + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, primary)


def load(primary=None, backup=None):
    primary, backup = Path(primary or PRIMARY), Path(backup or BACKUP)
    failures = []
    for path, fallback in ((Path(primary), False), (Path(backup), True)):
        try:
            payload = read_valid(path)
            return {"squads": payload["squads"], "fetched_at": payload["fetched_at"],
                    "fallback_used": fallback, "warning": "; ".join(failures) if fallback else None}
        except (OSError, ValueError, TypeError) as error:
            failures.append(f"{path.name}: {type(error).__name__}")
    return {"squads": {}, "fetched_at": None, "fallback_used": False,
            "warning": "No valid squad feed: " + "; ".join(failures)}
