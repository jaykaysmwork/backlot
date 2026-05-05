"""capture_batch.py — Auto-detect rooms and batch-capture each one.

Clusters game-logic actors spatially to find room centers, then runs
multi_look capture at each detected room. Works with any UE5 project.

Run from UE5's Python console:

    exec(open("<PROJECT_ROOT>/ue5_capture/capture_batch.py").read())

Config (set before exec):
    BATCH_MODE        = "multi_look"   # capture mode per room
    BATCH_N_FRAMES    = 20             # frames per room
    BATCH_CLUSTER_R   = 800.0          # clustering radius in cm
    BATCH_MIN_ACTORS  = 3              # min actors to form a room
    BATCH_DRY_RUN     = False          # True = detect only, don't capture
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import uuid
import time
from datetime import datetime, timezone

import unreal

_PROJECT_ROOT = globals().get("_PROJECT_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

for _name in [m for m in list(sys.modules) if m.startswith("ue5_capture")]:
    del sys.modules[_name]
import importlib
importlib.invalidate_caches()

from ue5_capture._unreal_helpers import make_rotator  # noqa: E402
from ue5_capture.annotate.actors import (  # noqa: E402
    collect_actors, BASE_SKIP_CLASSES,
    DEFAULT_EXTRA_SKIP_CLASSES, DEFAULT_SKIP_PREFIXES,
)
from ue5_capture.annotate.projection import PinholeProjector  # noqa: E402
from ue5_capture.capture.modalities import NATIVE_MODALITIES  # noqa: E402
from ue5_capture.capture.rig import CaptureRig  # noqa: E402
from ue5_capture.capture.telemetry import Stopwatch  # noqa: E402

# ═════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═════════════════════════════════════════════════════════════════════════════

OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "capture_output")
RESOLUTION_W = 1920
RESOLUTION_H = 1080
if sys.platform == "win32":
    VENV_PYTHON = os.path.join(_PROJECT_ROOT, ".venv", "Scripts", "python.exe")
else:
    VENV_PYTHON = os.path.join(_PROJECT_ROOT, ".venv", "bin", "python")
CONVERT_DEPTH_SCRIPT = os.path.join(_PROJECT_ROOT, "ue5_capture", "convert_depth.py")

BATCH_MODE = globals().get("BATCH_MODE", "multi_look")
BATCH_N_FRAMES = globals().get("BATCH_N_FRAMES", 20)
BATCH_CLUSTER_R = globals().get("BATCH_CLUSTER_R", 800.0)
BATCH_MIN_ACTORS = globals().get("BATCH_MIN_ACTORS", 3)
BATCH_DRY_RUN = globals().get("BATCH_DRY_RUN", False)

CAPTURE_SPREAD = globals().get("CAPTURE_SPREAD", 200.0)
CAPTURE_STOPS = globals().get("CAPTURE_STOPS", 4)
CAPTURE_RADIUS = globals().get("CAPTURE_RADIUS", 300.0)
CAPTURE_WALK_DISTANCE = globals().get("CAPTURE_WALK_DISTANCE", 800.0)
INDIRECT_LIGHT_BOOST = globals().get("CAPTURE_INDIRECT_LIGHT", 3.0)
EXPOSURE_BIAS = globals().get("CAPTURE_EXPOSURE_BIAS", 0.0)

_extra_skip = globals().get("CAPTURE_SKIP_CLASSES", DEFAULT_EXTRA_SKIP_CLASSES)
_skip_prefixes = tuple(globals().get("CAPTURE_SKIP_PREFIXES", DEFAULT_SKIP_PREFIXES))
_EFFECTIVE_SKIP = BASE_SKIP_CLASSES | frozenset(_extra_skip)
_EFFECTIVE_PREFIXES = _skip_prefixes


# ═════════════════════════════════════════════════════════════════════════════
#  ROOM DETECTION
# ═════════════════════════════════════════════════════════════════════════════

def _collect_positions(editor_actor):
    """Collect 3D positions of all non-skipped actors."""
    positions = []
    for actor in editor_actor.get_all_level_actors():
        klass = actor.get_class().get_name()
        if klass in _EFFECTIVE_SKIP:
            continue
        if any(klass.startswith(p) for p in _EFFECTIVE_PREFIXES):
            continue
        try:
            if actor.get_actor_label().startswith("_capture_rig_"):
                continue
        except Exception:
            pass
        try:
            origin, extent = actor.get_actor_bounds(True)
        except Exception:
            continue
        if extent.x == 0 and extent.y == 0 and extent.z == 0:
            continue
        positions.append((origin.x, origin.y, origin.z))
    return positions


def _cluster_rooms(positions, radius):
    """Simple greedy spatial clustering — no dependencies needed.

    Picks the densest unvisited point as a seed, gathers all points
    within radius, computes centroid, repeats.
    """
    remaining = list(range(len(positions)))
    clusters = []

    while remaining:
        best_seed = None
        best_count = 0
        for idx in remaining:
            px, py, pz = positions[idx]
            count = sum(
                1 for j in remaining
                if _dist2d(positions[idx], positions[j]) < radius
            )
            if count > best_count:
                best_count = count
                best_seed = idx

        if best_seed is None:
            break

        sx, sy, sz = positions[best_seed]
        members = [
            j for j in remaining
            if _dist2d(positions[best_seed], positions[j]) < radius
        ]

        cx = sum(positions[j][0] for j in members) / len(members)
        cy = sum(positions[j][1] for j in members) / len(members)
        cz = sum(positions[j][2] for j in members) / len(members)

        clusters.append({
            "center": (cx, cy, cz),
            "count": len(members),
        })

        remaining = [j for j in remaining if j not in set(members)]

    return clusters


def _dist2d(a, b):
    """XY distance — ignore Z so rooms on different floors stay separate only by XY."""
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return math.sqrt(dx * dx + dy * dy)


def detect_rooms(editor_actor, radius=BATCH_CLUSTER_R, min_actors=BATCH_MIN_ACTORS):
    """Return list of detected rooms sorted by actor count (largest first)."""
    positions = _collect_positions(editor_actor)
    print(f"[batch] {len(positions)} actors after filtering")

    if not positions:
        return []

    clusters = _cluster_rooms(positions, radius)
    rooms = [c for c in clusters if c["count"] >= min_actors]
    rooms.sort(key=lambda r: r["count"], reverse=True)

    for i, room in enumerate(rooms):
        room["label"] = f"room_{i + 1:03d}"
        cx, cy, cz = room["center"]
        print(f"  [{room['label']}] center=({cx:.0f}, {cy:.0f}, {cz:.0f}) actors={room['count']}")

    print(f"[batch] {len(rooms)} rooms detected (min_actors={min_actors}, radius={radius:.0f}cm)")
    return rooms


# ═════════════════════════════════════════════════════════════════════════════
#  TRAJECTORY (reuse from capture.py)
# ═════════════════════════════════════════════════════════════════════════════

def _compute_trajectory_multi_look(center, n_frames, spread=200.0, n_stops=4):
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    cx, cy, cz = center
    frames_per_stop = max(n_frames // n_stops, 1)
    poses = []
    for s in range(n_stops):
        angle = 2.0 * math.pi * s / n_stops
        sx = cx + spread * math.cos(angle)
        sy = cy + spread * math.sin(angle)
        sz = cz
        for j in range(frames_per_stop):
            t = j / max(frames_per_stop - 1, 1)
            pitch = -25.0 + 50.0 * t
            yaw = math.degrees(golden_angle * (s * frames_per_stop + j)) % 360
            poses.append({
                "x": round(sx, 2), "y": round(sy, 2), "z": round(sz, 2),
                "pitch": round(pitch, 2), "yaw": round(yaw, 2), "roll": 0.0,
            })
    remaining = n_frames - len(poses)
    for k in range(remaining):
        t = k / max(remaining - 1, 1)
        pitch = -15.0 + 30.0 * t
        yaw = math.degrees(golden_angle * (len(poses) + k)) % 360
        poses.append({
            "x": round(cx, 2), "y": round(cy, 2), "z": round(cz, 2),
            "pitch": round(pitch, 2), "yaw": round(yaw, 2), "roll": 0.0,
        })
    return poses


def _compute_trajectory_look_around(center, n_frames):
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    cx, cy, cz = center
    poses = []
    for i in range(n_frames):
        t = i / max(n_frames - 1, 1)
        pitch = -30.0 + 60.0 * t
        yaw = math.degrees(golden_angle * i) % 360
        poses.append({
            "x": round(cx, 2), "y": round(cy, 2), "z": round(cz, 2),
            "pitch": round(pitch, 2), "yaw": round(yaw, 2), "roll": 0.0,
        })
    return poses


def _compute_trajectory_sphere_interior(center, radius, n_frames):
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    cx, cy, cz = center
    poses = []
    for i in range(n_frames):
        t = i / max(n_frames - 1, 1)
        elevation = math.radians(-50.0 + 100.0 * t)
        azimuth = golden_angle * i
        px = cx + radius * math.cos(elevation) * math.cos(azimuth)
        py = cy + radius * math.cos(elevation) * math.sin(azimuth)
        pz = cz + radius * math.sin(elevation)
        dx, dy, dz = cx - px, cy - py, cz - pz
        yaw = math.degrees(math.atan2(dy, dx))
        horiz = math.sqrt(dx * dx + dy * dy)
        pitch = math.degrees(math.atan2(dz, horiz))
        poses.append({
            "x": round(px, 2), "y": round(py, 2), "z": round(pz, 2),
            "pitch": round(pitch, 2), "yaw": round(yaw, 2), "roll": 0.0,
        })
    return poses


def _compute_trajectory_walk_through(center, forward_yaw, n_frames, distance=800.0):
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    cx, cy, cz = center
    rad = math.radians(forward_yaw)
    dx = math.cos(rad) * distance
    dy = math.sin(rad) * distance
    poses = []
    for i in range(n_frames):
        t = i / max(n_frames - 1, 1)
        px = cx - dx / 2 + dx * t
        py = cy - dy / 2 + dy * t
        pz = cz
        yaw = math.degrees(golden_angle * i) % 360
        pitch = -20.0 + 40.0 * t
        poses.append({
            "x": round(px, 2), "y": round(py, 2), "z": round(pz, 2),
            "pitch": round(pitch, 2), "yaw": round(yaw, 2), "roll": 0.0,
        })
    return poses


def _compute_trajectory_random_walk(start, n_frames, step_cm=150.0):
    import random
    rng = random.Random(42)
    sx, sy, sz = start
    px, py, pz = sx, sy, sz
    poses = []
    for i in range(n_frames):
        yaw = rng.uniform(0.0, 360.0)
        yaw_rad = math.radians(yaw)
        step = rng.uniform(step_cm * 0.5, step_cm * 1.5)
        px += step * math.cos(yaw_rad)
        py += step * math.sin(yaw_rad)
        pz += rng.uniform(-step_cm * 0.15, step_cm * 0.15)
        look_yaw = yaw + rng.uniform(-30.0, 30.0)
        look_pitch = rng.uniform(-15.0, 5.0)
        poses.append({
            "x": round(px, 2), "y": round(py, 2), "z": round(pz, 2),
            "pitch": round(look_pitch, 2), "yaw": round(look_yaw, 2), "roll": 0.0,
        })
    return poses


def _compute_trajectory_spline(center, radius, n_frames, n_control=6):
    import random
    rng = random.Random(42)
    cx, cy, cz = center
    ctrl = []
    for k in range(n_control):
        az = 2.0 * math.pi * k / n_control + rng.uniform(-0.3, 0.3)
        el = rng.uniform(math.radians(10.0), math.radians(60.0))
        r = radius * rng.uniform(0.8, 1.2)
        ctrl.append((
            cx + r * math.cos(el) * math.cos(az),
            cy + r * math.cos(el) * math.sin(az),
            cz + r * math.sin(el),
        ))
    ctrl.append(ctrl[0])

    def _catmull_rom(p0, p1, p2, p3, t):
        t2, t3 = t * t, t * t * t
        return (
            0.5*((2*p1[0])+(-p0[0]+p2[0])*t+(2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2+(-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3),
            0.5*((2*p1[1])+(-p0[1]+p2[1])*t+(2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2+(-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3),
            0.5*((2*p1[2])+(-p0[2]+p2[2])*t+(2*p0[2]-5*p1[2]+4*p2[2]-p3[2])*t2+(-p0[2]+3*p1[2]-3*p2[2]+p3[2])*t3),
        )

    n_seg = len(ctrl) - 1
    poses = []
    for i in range(n_frames):
        u = (i / max(n_frames - 1, 1)) * n_seg
        seg = min(int(u), n_seg - 1)
        t = u - seg
        p0 = ctrl[(seg - 1) % len(ctrl)]
        p1 = ctrl[seg]
        p2 = ctrl[(seg + 1) % len(ctrl)]
        p3 = ctrl[(seg + 2) % len(ctrl)]
        px, py, pz = _catmull_rom(p0, p1, p2, p3, t)
        dx, dy, dz = cx - px, cy - py, cz - pz
        yaw = math.degrees(math.atan2(dy, dx))
        horiz = math.sqrt(dx * dx + dy * dy)
        pitch = math.degrees(math.atan2(dz, horiz))
        poses.append({
            "x": round(px, 2), "y": round(py, 2), "z": round(pz, 2),
            "pitch": round(pitch, 2), "yaw": round(yaw, 2), "roll": 0.0,
        })
    return poses


# ═════════════════════════════════════════════════════════════════════════════
#  HELPERS (shared with capture.py)
# ═════════════════════════════════════════════════════════════════════════════

def _euler_to_quaternion(pitch_deg, yaw_deg, roll_deg=0.0):
    p = math.radians(pitch_deg) / 2
    y = math.radians(yaw_deg) / 2
    r = math.radians(roll_deg) / 2
    sp, cp = math.sin(p), math.cos(p)
    sy, cy = math.sin(y), math.cos(y)
    sr, cr = math.sin(r), math.cos(r)
    return {
        "x": round(sp * cy * cr - cp * sy * sr, 6),
        "y": round(cp * sy * cr + sp * cy * sr, 6),
        "z": round(cp * cy * sr - sp * sy * cr, 6),
        "w": round(cp * cy * cr + sp * sy * sr, 6),
    }


def _write_camera_json(frame_dir, frame_index, pose, fov):
    data = {
        "frame_index": frame_index,
        "position": {"x": pose["x"], "y": pose["y"], "z": pose["z"]},
        "rotation_euler": {"pitch": pose["pitch"], "yaw": pose["yaw"], "roll": pose["roll"]},
        "rotation_quaternion": _euler_to_quaternion(pose["pitch"], pose["yaw"], pose["roll"]),
        "fov": fov,
        "image_width": RESOLUTION_W,
        "image_height": RESOLUTION_H,
        "camera_convention": "ue5_x_fwd_y_right_z_up",
    }
    with open(os.path.join(frame_dir, "camera.json"), "w") as f:
        json.dump(data, f, indent=2)


def _write_objects_json(frame_dir, frame_index, actors_data):
    data = {"frame_index": frame_index, "actor_count": len(actors_data), "actors": actors_data}
    with open(os.path.join(frame_dir, "objects.json"), "w") as f:
        json.dump(data, f, indent=2)


def _write_session_json(session_id, session_dir, scene_name, project_name,
                        frame_count, fov, unique_classes, modality_names):
    data = {
        "session_id": session_id,
        "scene_name": scene_name,
        "project_name": project_name,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "frame_count": frame_count,
        "config": {"resolution": [RESOLUTION_W, RESOLUTION_H], "fov_degrees": fov},
        "modalities": [("depth" if m == "depth_tmp" else m) for m in modality_names],
    }
    with open(os.path.join(session_dir, "session.json"), "w") as f:
        json.dump(data, f, indent=2)


def _clean_frames_root(frames_root):
    if not os.path.isdir(frames_root):
        return
    for name in os.listdir(frames_root):
        path = os.path.join(frames_root, name)
        if not os.path.isdir(path):
            continue
        for fname in os.listdir(path):
            try:
                os.remove(os.path.join(path, fname))
            except Exception:
                pass
        try:
            os.rmdir(path)
        except Exception:
            pass


def _run_depth_post_process(session_dir):
    if not os.path.isfile(VENV_PYTHON):
        return
    try:
        result = subprocess.run(
            [VENV_PYTHON, CONVERT_DEPTH_SCRIPT, session_dir],
            capture_output=True, text=True, timeout=120,
        )
        for line in result.stdout.splitlines():
            print(f"  {line}")
    except Exception as e:
        print(f"[post] FAILED: {e}")


def _run_ingestion(session_dir):
    if not os.path.isfile(VENV_PYTHON):
        return
    print(f"[ingest] auto-ingesting {session_dir}")
    try:
        result = subprocess.run(
            [VENV_PYTHON, "-m", "ingestion.ingest", session_dir],
            capture_output=True, text=True, timeout=120, cwd=_PROJECT_ROOT,
        )
        for line in result.stdout.splitlines():
            print(f"  {line}")
        if result.returncode != 0:
            for line in result.stderr.splitlines():
                print(f"  {line}")
    except Exception as e:
        print(f"[ingest] FAILED: {e}")


# ═════════════════════════════════════════════════════════════════════════════
#  CAPTURE ONE ROOM
# ═════════════════════════════════════════════════════════════════════════════

def _capture_room(room, project_name, level_name, ue_editor, editor_actor, fov):
    """Capture a single room and return stats."""
    label = room["label"]
    center = room["center"]
    folder_name = f"{level_name}_{label}"
    session_dir = os.path.join(OUTPUT_DIR, project_name, folder_name)

    existing_session = os.path.join(session_dir, "session.json")
    if os.path.isfile(existing_session):
        with open(existing_session) as f:
            session_id = json.load(f)["session_id"]
    else:
        session_id = str(uuid.uuid4())

    frames_root = os.path.join(session_dir, "frames")
    os.makedirs(frames_root, exist_ok=True)
    _clean_frames_root(frames_root)

    if BATCH_MODE == "look_around":
        trajectory = _compute_trajectory_look_around(center, BATCH_N_FRAMES)
        mode_label = "look-around"
    elif BATCH_MODE == "sphere_interior":
        trajectory = _compute_trajectory_sphere_interior(center, CAPTURE_RADIUS, BATCH_N_FRAMES)
        mode_label = "sphere-interior"
    elif BATCH_MODE == "walk_through":
        trajectory = _compute_trajectory_walk_through(center, 0.0, BATCH_N_FRAMES, CAPTURE_WALK_DISTANCE)
        mode_label = "walk-through"
    elif BATCH_MODE == "random_walk":
        step = globals().get("CAPTURE_STEP_CM", 150.0)
        trajectory = _compute_trajectory_random_walk(center, BATCH_N_FRAMES, step)
        mode_label = "random-walk"
    elif BATCH_MODE == "spline":
        spline_r = globals().get("CAPTURE_SPLINE_RADIUS", CAPTURE_RADIUS)
        n_ctrl = globals().get("CAPTURE_SPLINE_POINTS", 6)
        trajectory = _compute_trajectory_spline(center, spline_r, BATCH_N_FRAMES, n_ctrl)
        mode_label = "spline"
    else:
        trajectory = _compute_trajectory_multi_look(center, BATCH_N_FRAMES, CAPTURE_SPREAD, CAPTURE_STOPS)
        mode_label = "multi-look"

    print(f"\n  [{label}] {mode_label} | center=({center[0]:.0f},{center[1]:.0f},{center[2]:.0f}) | {len(trajectory)} frames")

    rig = CaptureRig(width=RESOLUTION_W, height=RESOLUTION_H, fov=fov, modalities=NATIVE_MODALITIES, indirect_light_boost=INDIRECT_LIGHT_BOOST, exposure_bias=EXPOSURE_BIAS)

    unique_classes = set()

    try:
        for i, pose in enumerate(trajectory):
            frame_dir = os.path.join(frames_root, f"frame_{i:03d}")
            os.makedirs(frame_dir, exist_ok=True)

            loc = unreal.Vector(pose["x"], pose["y"], pose["z"])
            rot = make_rotator(pose["pitch"], pose["yaw"], pose["roll"])
            rig.move_to(loc, rot)
            ue_editor.set_level_viewport_camera_info(loc, rot)

            rig.capture_all()
            rig.export_all(frame_dir)

            _write_camera_json(frame_dir, i, pose, fov)
            projector = PinholeProjector(pose, RESOLUTION_W, RESOLUTION_H, fov)
            all_actors = collect_actors(editor_actor, projector, _EFFECTIVE_SKIP, _EFFECTIVE_PREFIXES)
            visible_actors = [a for a in all_actors if "bbox_2d" in a]
            _write_objects_json(frame_dir, i, visible_actors)
            unique_classes.update(a["class"] for a in visible_actors)

        _write_session_json(
            session_id, session_dir, folder_name, project_name,
            len(trajectory), fov, unique_classes, rig.modality_names,
        )
        print(f"  [{label}] done — {len(trajectory)} frames, {len(unique_classes)} classes")
    finally:
        rig.cleanup()

    _run_depth_post_process(session_dir)
    _run_ingestion(session_dir)

    return {"label": label, "frames": len(trajectory), "classes": len(unique_classes)}


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════════

def _get_project_name():
    project_dir = unreal.Paths.project_dir()
    uproject = [f for f in os.listdir(project_dir) if f.endswith(".uproject")]
    if uproject:
        return os.path.splitext(uproject[0])[0]
    return os.path.basename(project_dir.rstrip("/"))


def _get_level_name():
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
        name = world.get_name()
        if name.startswith("UEDPIE_"):
            name = name.split("_", 2)[-1]
        return name
    except Exception:
        return "default"


def _load_world_partition():
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        return
    editor_actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    before = len(editor_actor.get_all_level_actors())
    actor_classes = set(a.get_class().get_name() for a in editor_actor.get_all_level_actors())
    if "WorldPartitionMiniMap" not in actor_classes:
        print(f"[wp] not a World Partition map ({before} actors)")
        return
    print(f"[wp] World Partition detected ({before} actors before load)")

    try:
        unreal.SystemLibrary.execute_console_command(world, "wp.Runtime.EnableStreaming 0")
        print("[wp] disabled WP runtime streaming")
    except Exception:
        pass

    try:
        wplib = unreal.WorldPartitionBlueprintLibrary
        huge = unreal.BoxBounds(
            unreal.Vector(-1e7, -1e7, -1e7),
            unreal.Vector(1e7, 1e7, 1e7),
        )
        descs = wplib.get_intersecting_actor_descs(huge)
        if descs and len(descs) > 0:
            guids = [d.get_editor_property("guid") for d in descs]
            print(f"[wp] loading {len(guids)} WP actors (giant bounds)...")
            wplib.load_actors(guids)
            wplib.pin_actors(guids)
            after = len(editor_actor.get_all_level_actors())
            print(f"[wp] loaded & pinned — {after} actors (was {before})")
        else:
            raise RuntimeError("fallback")
    except Exception:
        try:
            wplib = unreal.WorldPartitionBlueprintLibrary
            bounds = wplib.get_editor_world_bounds()
            descs = wplib.get_intersecting_actor_descs(bounds)
            if descs and len(descs) > 0:
                guids = [d.get_editor_property("guid") for d in descs]
                print(f"[wp] loading {len(guids)} WP actors (editor bounds)...")
                wplib.load_actors(guids)
                wplib.pin_actors(guids)
                after = len(editor_actor.get_all_level_actors())
                print(f"[wp] loaded & pinned — {after} actors (was {before})")
        except Exception as e:
            print(f"[wp] auto-load failed: {e}")

    time.sleep(2.0)
    final = len(editor_actor.get_all_level_actors())
    print(f"[wp] final actor count: {final}")


def run_batch():
    project_name = _get_project_name()
    level_name = _get_level_name()

    print(f"\n{'═' * 60}")
    print(f"Backlot Batch Capture")
    print(f"  Project : {project_name}")
    print(f"  Level   : {level_name}")
    print(f"  Mode    : {BATCH_MODE}")
    print(f"  Frames  : {BATCH_N_FRAMES} per room")
    print(f"  Cluster : radius={BATCH_CLUSTER_R:.0f}cm, min_actors={BATCH_MIN_ACTORS}")
    print(f"{'═' * 60}\n")

    _load_world_partition()

    ue_editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    editor_actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    rooms = detect_rooms(editor_actor, BATCH_CLUSTER_R, BATCH_MIN_ACTORS)

    if not rooms:
        print("[batch] no rooms detected — nothing to capture")
        return

    if BATCH_DRY_RUN:
        print(f"\n[batch] DRY RUN — {len(rooms)} rooms detected, skipping capture")
        return

    fov = 90.0
    try:
        fov = float(ue_editor.get_level_viewport_camera_info()[2])
    except Exception:
        pass

    # Warmup: fire throwaway captures at the first room center so WP cells
    # finish streaming and Lumen GI accumulates initial indirect lighting.
    first_center = rooms[0]["center"]
    warmup_loc = unreal.Vector(*first_center)
    warmup_rot = make_rotator(0.0, 0.0, 0.0)
    warmup_rig = CaptureRig(width=RESOLUTION_W, height=RESOLUTION_H, fov=fov, modalities=NATIVE_MODALITIES, indirect_light_boost=INDIRECT_LIGHT_BOOST, exposure_bias=EXPOSURE_BIAS)
    warmup_rig.move_to(warmup_loc, warmup_rot)
    ue_editor.set_level_viewport_camera_info(warmup_loc, warmup_rot)
    WARMUP_FRAMES = 5
    for wi in range(WARMUP_FRAMES):
        warmup_rig.capture_all()
        time.sleep(0.5)
    warmup_rig.cleanup()
    print(f"[warmup] {WARMUP_FRAMES} throwaway captures done — WP + Lumen primed")

    results = []
    for i, room in enumerate(rooms):
        print(f"\n[batch] room {i + 1}/{len(rooms)}")
        stats = _capture_room(room, project_name, level_name, ue_editor, editor_actor, fov)
        results.append(stats)

    # Re-enable WP streaming
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
        unreal.SystemLibrary.execute_console_command(world, "wp.Runtime.EnableStreaming 1")
    except Exception:
        pass

    print(f"\n{'═' * 60}")
    print(f"Batch Capture Complete — {len(results)} rooms")
    for r in results:
        print(f"  {r['label']}: {r['frames']} frames, {r['classes']} classes")
    total_frames = sum(r["frames"] for r in results)
    print(f"  total: {total_frames} frames")
    print(f"{'═' * 60}\n")


run_batch()
