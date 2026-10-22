import shutil
from pathlib import Path

import pytest

REAL_MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "churn-v1"


@pytest.fixture
def model_dir(tmp_path: Path) -> Path:
    """A writable copy of the real artifact so tests can corrupt it freely."""
    target = tmp_path / "churn-v1"
    shutil.copytree(REAL_MODEL_DIR, target)
    return target
