"""Actor iteration + filtering + 3D bounds + 2D bbox projection.

Walks the editor world, drops environmental actors (lights/fog/volumes) and
the capture rig's own actors, then emits per-actor metadata:

  - name, class
  - world_position  (center of actor)
  - bounds_3d       (origin + half-extent, world-space AABB)
  - bbox_2d         (x, y, width, height, min_depth_cm) — projected via the
                     PinholeProjector; absent when the actor is entirely
                     behind the camera or clipped off-screen.
"""

from __future__ import annotations

from typing import List, Optional

import unreal

from .projection import PinholeProjector


BASE_SKIP_CLASSES = frozenset({
    "WorldSettings", "SkyAtmosphere", "DirectionalLight", "LocalFogVolume",
    "SkyLight", "ExponentialHeightFog", "AtmosphericFog", "PostProcessVolume",
    "LightmassImportanceVolume", "PlayerStart", "NavMeshBoundsVolume",
    "ReflectionCapture", "SphereReflectionCapture", "BoxReflectionCapture",
    "DecalActor", "LevelSequenceActor",
    "LevelInstance", "WorldPartitionHLOD", "WorldDataLayers",
    "CameraRig_Rail", "CameraRig_Crane",
    "Note",
})

DEFAULT_EXTRA_SKIP_CLASSES = [
    "StaticMeshActor", "BakedStaticMeshActor_C",
    "BlockingVolume", "TriggerBox", "TriggerSphere", "TriggerVolume",
    "PainCausingVolume", "KillZVolume", "PhysicsVolume",
    "NavLinkProxy", "NavigationData", "AbstractNavData",
]

DEFAULT_SKIP_PREFIXES = ["B_Tool_"]

SKIP_CLASSES = BASE_SKIP_CLASSES | frozenset(DEFAULT_EXTRA_SKIP_CLASSES)
_SKIP_PREFIXES = tuple(DEFAULT_SKIP_PREFIXES)


_RIG_LABEL_PREFIX = "_capture_rig_"


def collect_actors(
    editor_actor: "unreal.EditorActorSubsystem",
    projector: Optional[PinholeProjector] = None,
    skip_classes: Optional[frozenset] = None,
    skip_prefixes: Optional[tuple] = None,
) -> List[dict]:
    """Return per-visible-actor metadata dicts.

    If ``projector`` is provided, each entry gets a ``bbox_2d`` field when the
    actor's AABB projects into the image; actors with no visible AABB are
    still emitted (without ``bbox_2d``) so downstream consumers can count
    scene population.
    """
    _skip = skip_classes if skip_classes is not None else SKIP_CLASSES
    _prefixes = skip_prefixes if skip_prefixes is not None else _SKIP_PREFIXES
    out: List[dict] = []
    for actor in editor_actor.get_all_level_actors():
        klass = actor.get_class().get_name()
        if klass in _skip:
            continue
        if _prefixes and any(klass.startswith(p) for p in _prefixes):
            continue
        try:
            if actor.get_actor_label().startswith(_RIG_LABEL_PREFIX):
                continue
        except Exception:
            pass

        try:
            loc = actor.get_actor_location()
            origin, extent = actor.get_actor_bounds(True)
        except Exception as e:
            print(f"  [actors] skip {actor.get_name()}: {e}")
            continue

        entry = {
            "name": actor.get_name(),
            "class": klass,
            "world_position": {
                "x": round(loc.x, 2),
                "y": round(loc.y, 2),
                "z": round(loc.z, 2),
            },
            "bounds_3d": {
                "origin": {
                    "x": round(origin.x, 2),
                    "y": round(origin.y, 2),
                    "z": round(origin.z, 2),
                },
                "extent": {
                    "x": round(extent.x, 2),
                    "y": round(extent.y, 2),
                    "z": round(extent.z, 2),
                },
            },
        }

        if projector is not None:
            bbox = projector.project_aabb(
                (origin.x, origin.y, origin.z),
                (extent.x, extent.y, extent.z),
            )
            if bbox is not None:
                entry["bbox_2d"] = bbox

        out.append(entry)

    return out
