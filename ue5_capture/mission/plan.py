"""MissionPlan Pydantic model.

A MissionPlan is a declarative capture plan: what scene, which modalities,
what camera trajectory strategies, what coverage goals and constraints.

The full schema (including A-tier fields like semantic_target, coverage_goals,
constraints) is defined here with A-only fields marked ``Optional`` so that
B-scope missions validate against the same schema, and A extensions are
additive (no rewrite).

Populated in Phase P1.4 and P1.6.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover - Pydantic installed in env
    raise


Vec3 = Tuple[float, float, float]


class MissionPlan(BaseModel):
    """Declarative capture plan. Full fields filled in P1.6."""

    name: str
    version: int = 1
    scene: str

    # Filled out through P1.4 / P1.6 / P1.7
    # resolution: Tuple[int, int]
    # fov: float
    # modalities: List[str]
    # strategies: List[Dict[str, Any]]
    # coverage_goals: Optional[Dict[str, Any]] = None   # A-tier extension hook
    # constraints: Optional[Dict[str, Any]] = None      # A-tier extension hook
