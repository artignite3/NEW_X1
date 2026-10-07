"""Configurable artifact locations shared by the API and isolated pipeline stages."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def data_root():
    return Path(os.path.abspath(os.getenv("NEW_X1_DATA_ROOT", str(PROJECT_ROOT / "data"))))


def model_root():
    return Path(os.path.abspath(os.getenv("NEW_X1_MODEL_ROOT", str(PROJECT_ROOT / "model_artifacts"))))
