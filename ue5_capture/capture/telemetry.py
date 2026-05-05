"""Per-frame capture telemetry.

Records timings + per-modality export success per frame. Emitted as part of
session.json so the demo can show "synchronized telemetry" as an audit
artifact. P1.2 captures just capture-ms + export-ms + modalities_ok; P1.4
adds schema-backed provenance tie-in.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class FrameTelemetry:
    frame_index: int
    capture_ms: float = 0.0
    export_ms: float = 0.0
    annotate_ms: float = 0.0
    modalities_ok: Dict[str, bool] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "frame_index": self.frame_index,
            "capture_ms": round(self.capture_ms, 2),
            "export_ms": round(self.export_ms, 2),
            "annotate_ms": round(self.annotate_ms, 2),
            "modalities_ok": dict(self.modalities_ok),
        }


class Stopwatch:
    """Minimal perf_counter wrapper for laps in ms."""

    def __init__(self) -> None:
        self._t0 = time.perf_counter()

    def lap_ms(self) -> float:
        t = time.perf_counter()
        dt = (t - self._t0) * 1000.0
        self._t0 = t
        return dt
