"""LLM-backed mission generator — interface stub.

A natural-language capture brief + scene metadata → a MissionPlan. The
signature is fixed here so plugging in a real LLM call is a pure body swap.
"""

from __future__ import annotations

from typing import Any, Dict

from .plan import MissionPlan


def generate_mission_from_brief(brief: str, scene_info: Dict[str, Any]) -> MissionPlan:
    """Translate a natural-language brief into a MissionPlan.

    Args:
        brief: e.g. "a sweeping orbit around the hub with a top-down overview"
        scene_info: {actor_counts_by_class, scene_bbox, unique_classes}

    Returns:
        A validated MissionPlan.
    """
    raise NotImplementedError(
        "llm_generator stub: plug a real LLM call here. "
        "For now, load missions/hub_orbit.py or missions/auto_spline.py directly."
    )
