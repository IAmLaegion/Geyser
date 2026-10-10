import os
from pathlib import Path


def data_dir() -> Path:
    """Per-user folder for settings and history. GEYSER_DATA_DIR overrides it (used by tools/preview.py)."""
    override = os.environ.get("GEYSER_DATA_DIR")
    if override:
        path = Path(override)
    else:
        path = Path(os.environ.get("APPDATA") or Path.home()) / "Geyser"
    path.mkdir(parents=True, exist_ok=True)
    return path
