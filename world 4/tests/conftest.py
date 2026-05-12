"""pytest config for W4 pipeline tests."""
from __future__ import annotations
import sys
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1] / "pipeline"
sys.path.insert(0, str(PIPELINE))
