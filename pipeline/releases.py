"""Immutable checked releases, conditional promotion, and whole-release recovery."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import shutil
from uuid import uuid4
from pipeline.object_store import json_bytes, valid_key
from model.data_contract import FEATURE_SCHEMA_VERSION, TRAIN_CUTOFF

REQUIRED = tuple([
    name for fmt in ("t20", "odi", "test")
    for name in (f"data/processed/player_fantasy_points_{fmt}.json", f"data/processed/features_{fmt}.parquet")
] + ["data/future_matches/upcoming_matches.json", "data/future_matches/upcoming_squads.json",
     "model_artifacts/ProductUI_Model", "model_artifacts/ProductUI_Model_meta.pkl",
     "model_artifacts/tribe_odi.pkl", "model_artifacts/tribe_test.pkl"])
OPTIONAL = tuple(f"data/processed/ingestion_{fmt}.json" for fmt in ("t20", "odi", "test")) + ("data/venue_history.json",)
ALLOWED = set(REQUIRED + OPTIONAL)


def sha256(path):
    with Path(path).open("rb") as handle: return hashlib.file_digest(handle, "sha256").hexdigest()


def validate_runtime(root):
    result = subprocess.run([sys.executable, "-m", "pipeline.validate_release", "--root", str(root)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=600)
    if result.returncode: raise ValueError("Release failed data/model contract validation")
    return json.loads(result.stdout.strip().splitlines()[-1])


def check_manifest(manifest):
    if (not isinstance(manifest, dict) or manifest.get("schema") != FEATURE_SCHEMA_VERSION
        or manifest.get("cutoff") != TRAIN_CUTOFF
        or not re.fullmatch(r"[a-f0-9]{32}", str(manifest.get("release_id", "")))):
        raise ValueError("Invalid release contract")
    created = datetime.fromisoformat(manifest["created_at"])
    if created.tzinfo is None or created > datetime.now(timezone.utc):
        raise ValueError("Release time must be a past/present timezone-aware value")
    files = manifest.get("files")
    if not isinstance(files, dict) or not set(REQUIRED).issubset(files) or set(files) - ALLOWED:
        raise ValueError("Release file set is incomplete or unrecognized")
    for name, item in files.items():
        valid_key(name)
        if (not isinstance(item, dict) or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("sha256", "")))
            or type(item.get("bytes")) is not int or not 0 < item["bytes"] <= 2_000_000_000):
            raise ValueError("Invalid file checksum/size")
    return manifest


def read_pointer(store):
    raw, etag = store.read("current.json")
    if raw is None: return {"current": None, "previous": None}, etag
    pointer = json.loads(raw)
    if not isinstance(pointer, dict): raise ValueError("Invalid release pointer")
    for field in ("current", "previous"):
        value = pointer.get(field)
        if value is not None and not re.fullmatch(r"releases/[a-f0-9]{32}\.json", str(value)):
            raise ValueError("Invalid release reference")
    return pointer, etag


def publish_release(root, store, *, pointer=None, etag=None, validator=validate_runtime, status="ok"):
    """Freeze the candidate before validation/hashing so uploads cannot mix writes."""
    root = Path(root).resolve()
    if pointer is None: pointer, etag = read_pointer(store)
    with tempfile.TemporaryDirectory(prefix="new-x1-publish-") as folder:
        frozen = Path(folder)
        for name in REQUIRED + OPTIONAL:
            source = root / name
            if not source.is_file() or not source.resolve().is_relative_to(root):
                if name in REQUIRED: raise ValueError(f"Required release file missing/unsafe: {name}")
                continue
            destination = frozen / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        return _publish_frozen(frozen, store, pointer, etag, validator, status)


def _publish_frozen(root, store, pointer, etag, validator, status):
    # All models and histories must validate together before changing the pointer.
    validation = validator(root)
    manifest = {"release_id": uuid4().hex, "created_at": datetime.now(timezone.utc).isoformat(),
        "schema": FEATURE_SCHEMA_VERSION, "cutoff": TRAIN_CUTOFF, "pipeline_status": status,
        "validation": validation, "files": {}}
    for name in REQUIRED + OPTIONAL:
        source = root / name
        if not source.is_file():
            if name in REQUIRED: raise ValueError(f"Required release file missing: {name}")
            continue
        digest = sha256(source)
        manifest["files"][name] = {"sha256": digest, "bytes": source.stat().st_size}
        # Identical files share one blob across releases. Private writer access is required.
        store.put_file("blobs/" + digest, source)
    check_manifest(manifest)
    key = "releases/" + manifest["release_id"] + ".json"
    store.write(key, json_bytes(manifest))
    next_pointer = {"current": key, "previous": pointer.get("current")}
    store.write("current.json", json_bytes(next_pointer), conditional=True, expected=etag)
    return manifest


def restore_manifest(store, key, cache, *, validator=validate_runtime):
    if not re.fullmatch(r"releases/[a-f0-9]{32}\.json", str(key)): raise ValueError("Invalid release reference")
    raw, _ = store.read(key)
    if raw is None: raise ValueError("Release manifest is unavailable")
    manifest = check_manifest(json.loads(raw))
    if key != "releases/" + manifest["release_id"] + ".json": raise ValueError("Release identity mismatch")
    cache = Path(cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / manifest["release_id"]
    if destination.exists():
        verify_files(destination, manifest)
        validator(destination)
        return destination, manifest
    with tempfile.TemporaryDirectory(prefix="restore-", dir=cache) as folder:
        stage = Path(folder) / "release"
        stage.mkdir()
        for name, info in manifest["files"].items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            store.download("blobs/" + info["sha256"], path)
        verify_files(stage, manifest)
        validator(stage)
        os.replace(stage, destination)
    return destination, manifest


def verify_files(root, manifest):
    for name, info in manifest["files"].items():
        path = root / name
        if (not path.is_file() or not path.resolve().is_relative_to(root.resolve())
            or path.stat().st_size != info["bytes"] or sha256(path) != info["sha256"]):
            raise ValueError("Release checksum verification failed")


def restore_release(store, cache, *, validator=validate_runtime):
    pointer, etag = read_pointer(store)
    failures = []
    for key in dict.fromkeys([pointer.get("current"), pointer.get("previous")]):
        if not key: continue
        try:
            root, manifest = restore_manifest(store, key, cache, validator=validator)
            return root, manifest, {"fallback_used": key != pointer.get("current"), "failures": failures,
                                    "pointer": pointer, "etag": etag, "selected": key}
        except Exception as error:
            failures.append(type(error).__name__)
    raise ValueError("No verified release available (" + ", ".join(failures) + ")")


def rollback(store, *, validator=validate_runtime):
    pointer, etag = read_pointer(store)
    if not pointer.get("previous"): raise ValueError("No previous release to restore")
    # Validate and checksum the recovery target before promoting it.
    with tempfile.TemporaryDirectory(prefix="new-x1-rollback-") as cache:
        restore_manifest(store, pointer["previous"], cache, validator=validator)
    store.write("current.json", json_bytes({"current": pointer["previous"], "previous": pointer["current"]}),
                conditional=True, expected=etag)


def main():
    import argparse
    from dotenv import load_dotenv
    from pipeline.object_store import configured_store
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["seed", "restore", "rollback"])
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--cache", default="outputs/releases")
    args = parser.parse_args()
    store = configured_store()
    if args.action == "seed":
        from pipeline.runtime import exclusive_lock
        with exclusive_lock(Path(args.root).resolve() / "data/pipeline.lock"):
            print(publish_release(args.root, store)["release_id"])
    elif args.action == "restore":
        root, manifest, recovery = restore_release(store, args.cache)
        print(json.dumps({"root": str(root), "release_id": manifest["release_id"], "fallback_used": recovery["fallback_used"]}))
    else: rollback(store); print("Previous verified release promoted")


if __name__ == "__main__": main()
