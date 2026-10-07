"""Seed local last-good snapshots from currently validated artifacts.

Run once after installing or restoring a checkout. Existing snapshots are left
untouched, so an older known-good version remains available after bad updates.
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.future_matches import fixture_store, squad_store
from data_processing.safe_publish import last_good
from model import predict_model, team_generator


def seed(primary, backup):
    if backup.exists():
        return False
    staged = backup.with_name(backup.name + ".tmp")
    shutil.copyfile(primary, staged)
    os.replace(staged, backup)
    print(f"Seeded {backup.relative_to(ROOT)}")
    return True


def main():
    fixture_store.read_valid(fixture_store.PRIMARY)
    squad_store.read_valid(squad_store.PRIMARY)
    targets = [(fixture_store.PRIMARY, fixture_store.BACKUP),
               (squad_store.PRIMARY, squad_store.BACKUP)]

    for fmt in ("t20", "odi", "test"):
        predict_model.get_model(fmt)
        predict_model._load_features_dataset(fmt)
        team_generator.get_fantasy(fmt)
        if any(source != "current" for source in (
                predict_model._MODEL_SOURCES[fmt], predict_model._DF_SOURCES[fmt],
                team_generator._FANTASY_SOURCES[fmt])):
            raise ValueError(f"{fmt}: current artifact is invalid; refusing to seed from fallback")
        artifact = (ROOT / "model_artifacts" / "ProductUI_Model" if fmt == "t20"
                    else ROOT / "model_artifacts" / f"tribe_{fmt}.pkl")
        targets.append((artifact, last_good(artifact)))
        if fmt == "t20":
            meta = ROOT / "model_artifacts" / "ProductUI_Model_meta.pkl"
            targets.append((meta, last_good(meta)))
        for stem in (f"features_{fmt}.parquet", f"player_fantasy_points_{fmt}.json"):
            path = ROOT / "data" / "processed" / stem
            targets.append((path, last_good(path)))

    team_generator.get_datewise_json()
    if team_generator._DATEWISE_SOURCE != "current":
        raise ValueError("Datewise squad history is not current")
    datewise = ROOT / "data" / "processed" / "datewise_squad.json"
    targets.append((datewise, last_good(datewise)))
    for primary, backup in targets:
        seed(primary, backup)
    print(f"Verified {len(targets)} primary artifacts and their backups")


if __name__ == "__main__":
    main()
