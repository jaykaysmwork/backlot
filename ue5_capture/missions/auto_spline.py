"""Automated spline-path mission.

A Catmull-Rom spline sampled at N waypoints, with look-at vectors resolved
either from fixed targets or from nearby actor clusters. Demonstrates that
the Mission System can generate capture plans without manual camera placement.
"""

MISSION = {
    "name": "stackobot-auto-spline-v1",
    "version": 1,
    "scene": "StackOBot",
}
