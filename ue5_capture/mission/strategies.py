"""Camera trajectory strategies.

Strategy is an abstract base. Concrete strategies expand a strategy spec into
a list of concrete camera poses. Keeping the ABC even for B-scope (where only
Orbit / Waypoints / Spline exist) keeps the A extension (SemanticTarget) a
pure add-on — one new class, zero refactor.

Populated in Phase P1.6.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple


CameraPose = Dict[str, float]  # {x, y, z, pitch, yaw, roll?}


class Strategy(ABC):
    """Abstract base — A extension (SemanticTargetStrategy) plugs in here."""

    type_name: str = ""

    @abstractmethod
    def expand(self, spec: Dict[str, Any]) -> List[CameraPose]:
        """Take a strategy dict from a MissionPlan, return concrete poses."""


# TODO(P1.6): OrbitStrategy, WaypointsStrategy, SplineStrategy
# TODO(A): SemanticTargetStrategy
