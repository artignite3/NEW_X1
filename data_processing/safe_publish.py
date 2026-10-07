"""Atomically promote a prepared file while retaining one previous copy."""
import os
import shutil
from pathlib import Path


def last_good(path: Path) -> Path:
    path = Path(path)
    return path.with_name(path.name + ".last_good")


def promote(prepared: Path, destination: Path, *, validate=None, preserve_current=True) -> None:
    prepared, destination = Path(prepared), Path(destination)
    if not prepared.is_file() or prepared.stat().st_size == 0:
        raise ValueError(f"Prepared artifact missing or empty: {prepared}")
    if validate:
        validate(prepared)
    destination.parent.mkdir(parents=True, exist_ok=True)
    preserve_current = preserve_current and destination.is_file() and destination.stat().st_size > 0
    if preserve_current and validate:
        try:
            validate(destination)
        except Exception:
            preserve_current = False
    if preserve_current:
        previous = last_good(destination)
        staging = previous.with_name(previous.name + ".tmp")
        shutil.copyfile(destination, staging)
        os.replace(staging, previous)
    os.replace(prepared, destination)
