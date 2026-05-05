"""Small UE5-specific helpers shared across modules."""

import unreal


def make_rotator(pitch: float, yaw: float, roll: float = 0.0) -> "unreal.Rotator":
    """Construct a Rotator by explicit field assignment.

    ``unreal.Rotator(...)`` positional-argument order varies across UE minor
    versions (some ``(pitch, yaw, roll)``, some ``(roll, pitch, yaw)``).
    Assigning fields by name sidesteps the ambiguity.
    """
    r = unreal.Rotator()
    r.pitch = float(pitch)
    r.yaw = float(yaw)
    r.roll = float(roll)
    return r
