import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

_default_data = _PROJECT_ROOT / "capture_output"
if not _default_data.is_dir():
    _default_data = _PROJECT_ROOT / "sample_data"

CAPTURE_OUTPUT_DIR = os.environ.get(
    "CAPTURE_OUTPUT_DIR",
    str(_default_data),
)
