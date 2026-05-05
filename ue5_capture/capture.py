"""capture.py — Entry point for the Backlot capture engine.

Run from UE5's Python console:

    exec(open("<PROJECT_ROOT>/ue5_capture/capture.py").read())

4 UE-native modalities: rgb, depth_tmp (HDR float), normal, base_color.
Subsystem API throughout (EditorActorSubsystem, UnrealEditorSubsystem).
Post-capture ``depth_tmp.exr → {depth.png, depth.exr}`` runs in the host venv.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

import unreal


# ═════════════════════════════════════════════════════════════════════════════
#  sys.path setup — so ue5_capture/* modules are importable when this script is
#  run via ``exec(open(...).read())`` from the UE5 Python console.
# ═════════════════════════════════════════════════════════════════════════════

_PROJECT_ROOT = globals().get("_PROJECT_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Force-reload our modules on every script run (UE5 Python caches imports
# between `exec` calls; stale modules would mask edits during iterative dev).
for _name in [m for m in list(sys.modules) if m.startswith("ue5_capture")]:
    del sys.modules[_name]
import importlib
importlib.invalidate_caches()

from ue5_capture._unreal_helpers import make_rotator  # noqa: E402
from ue5_capture.annotate.actors import (  # noqa: E402
    collect_actors, BASE_SKIP_CLASSES,
    DEFAULT_EXTRA_SKIP_CLASSES, DEFAULT_SKIP_PREFIXES,
)
from ue5_capture.annotate.projection import PinholeProjector, rotator_basis  # noqa: E402
from ue5_capture.capture.modalities import NATIVE_MODALITIES  # noqa: E402
from ue5_capture.capture.rig import CaptureRig  # noqa: E402
from ue5_capture.capture.telemetry import FrameTelemetry, Stopwatch  # noqa: E402

# Verify projection fix is loaded (up vector X should be positive for pitch=-45, yaw=0)
_fwd, _right, _up = rotator_basis(-45.0, 0.0, 0.0)
assert _up[0] > 0, f"STALE projection.py! up[0]={_up[0]}, expected positive"
print(f"[capture] projection check OK: up={_up}")


# ═════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═════════════════════════════════════════════════════════════════════════════

OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "capture_output")
RESOLUTION_W = 1920
RESOLUTION_H = 1080

# Post-process runs in the project venv (UE5's embedded Python lacks opencv).
if sys.platform == "win32":
    VENV_PYTHON = os.path.join(_PROJECT_ROOT, ".venv", "Scripts", "python.exe")
else:
    VENV_PYTHON = os.path.join(_PROJECT_ROOT, ".venv", "bin", "python")
CONVERT_DEPTH_SCRIPT = os.path.join(_PROJECT_ROOT, "ue5_capture", "convert_depth.py")

# ─────────────────────────────────────────────────────────────────────────────
#  Trajectory: Fibonacci hemisphere — uniform solid-angle coverage, always
#  looking at SCENE_CENTER. Golden-angle spacing avoids clustering at poles.
# ─────────────────────────────────────────────────────────────────────────────

N_FRAMES = globals().get("CAPTURE_N_FRAMES", 20)
CAPTURE_MODE = globals().get("CAPTURE_MODE", "orbit")   # orbit / look_around / multi_look / walk_through / sphere_interior / local_orbit
CAPTURE_LABEL = globals().get("CAPTURE_LABEL", None)     # sub-folder label for room captures
LOCAL_ORBIT_RADIUS = globals().get("CAPTURE_RADIUS", 400.0)  # cm, for local_orbit mode
INDIRECT_LIGHT_BOOST = globals().get("CAPTURE_INDIRECT_LIGHT", 3.0)  # indirect lighting multiplier
EXPOSURE_BIAS = globals().get("CAPTURE_EXPOSURE_BIAS", 0.0)         # EV offset: +1 = 2× brighter, -1 = 2× darker
ELEVATION_MIN_DEG = 10.0               # avoid ground-level grazing shots
ELEVATION_MAX_DEG = 70.0               # avoid pure top-down

# Configurable actor filtering — override to include/exclude specific classes
_extra_skip = globals().get("CAPTURE_SKIP_CLASSES", DEFAULT_EXTRA_SKIP_CLASSES)
_skip_prefixes = tuple(globals().get("CAPTURE_SKIP_PREFIXES", DEFAULT_SKIP_PREFIXES))
_EFFECTIVE_SKIP = BASE_SKIP_CLASSES | frozenset(_extra_skip)
_EFFECTIVE_PREFIXES = _skip_prefixes


def _compute_scene_bounds(editor_actor) -> tuple:
    """Compute scene center and orbit radius from level actors.

    Uses 10th–90th percentile of actor positions per axis to ignore
    outliers like giant cloud/decoration meshes.
    """
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

    if not positions:
        return (0.0, 0.0, 400.0), 6000.0

    n = len(positions)
    xs = sorted(p[0] for p in positions)
    ys = sorted(p[1] for p in positions)
    zs = sorted(p[2] for p in positions)

    lo = max(int(n * 0.10), 0)
    hi = min(int(n * 0.90), n - 1)

    cx = (xs[lo] + xs[hi]) / 2
    cy = (ys[lo] + ys[hi]) / 2
    cz = (zs[lo] + zs[hi]) / 2
    dx = xs[hi] - xs[lo]
    dy = ys[hi] - ys[lo]
    dz = zs[hi] - zs[lo]
    diagonal = math.sqrt(dx * dx + dy * dy + dz * dz)
    radius = max(min(diagonal * 0.75, 8000.0), 1000.0)

    print(f"[bounds] {n} actors, p10–p90 box: "
          f"({xs[lo]:.0f}..{xs[hi]:.0f}, {ys[lo]:.0f}..{ys[hi]:.0f}, {zs[lo]:.0f}..{zs[hi]:.0f})")

    return (cx, cy, cz), radius


def _compute_trajectory(center, orbit_radius, n_frames: int = N_FRAMES) -> list:
    """Fibonacci hemisphere: *n_frames* poses distributed on upper hemisphere."""
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    cx, cy, cz = center
    el_min = math.radians(ELEVATION_MIN_DEG)
    el_max = math.radians(ELEVATION_MAX_DEG)
    poses = []
    for i in range(n_frames):
        t = i / max(n_frames - 1, 1)
        elevation = el_min + (el_max - el_min) * t
        azimuth = golden_angle * i

        px = cx + orbit_radius * math.cos(elevation) * math.cos(azimuth)
        py = cy + orbit_radius * math.cos(elevation) * math.sin(azimuth)
        pz = cz + orbit_radius * math.sin(elevation)

        dx, dy, dz = cx - px, cy - py, cz - pz
        yaw = math.degrees(math.atan2(dy, dx))
        horiz = math.sqrt(dx * dx + dy * dy)
        pitch = math.degrees(math.atan2(dz, horiz))

        poses.append(
            {
                "x": round(px, 2),
                "y": round(py, 2),
                "z": round(pz, 2),
                "pitch": round(pitch, 2),
                "yaw": round(yaw, 2),
                "roll": 0.0,
            }
        )
    return poses


def _compute_trajectory_look_around(center, n_frames: int = N_FRAMES) -> list:
    """Camera stays at center, looks in uniformly distributed directions."""
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    cx, cy, cz = center
    poses = []
    for i in range(n_frames):
        t = i / max(n_frames - 1, 1)
        pitch = -30.0 + 60.0 * t
        yaw = math.degrees(golden_angle * i) % 360

        poses.append(
            {
                "x": round(cx, 2),
                "y": round(cy, 2),
                "z": round(cz, 2),
                "pitch": round(pitch, 2),
                "yaw": round(yaw, 2),
                "roll": 0.0,
            }
        )
    return poses


def _compute_trajectory_multi_look(
    center, n_frames: int = N_FRAMES, spread_cm: float = 200.0, n_stops: int = 4,
) -> list:
    """Move to n_stops points around center, do a mini look_around at each.

    Stop positions form a small ring (radius = spread_cm) around center at
    the same height. At each stop the camera rotates through evenly spaced
    yaw angles with slight pitch variation.
    """
    cx, cy, cz = center
    frames_per_stop = max(n_frames // n_stops, 1)
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    poses = []
    for s in range(n_stops):
        angle = 2.0 * math.pi * s / n_stops
        sx = cx + spread_cm * math.cos(angle)
        sy = cy + spread_cm * math.sin(angle)
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


def _compute_trajectory_walk_through(
    start, direction_deg, n_frames: int = N_FRAMES, distance_cm: float = 800.0,
) -> list:
    """Walk forward from start along direction_deg (yaw), with slight gaze variation."""
    import random
    rng = random.Random(42)
    sx, sy, sz = start
    yaw_rad = math.radians(direction_deg)
    fwd_x = math.cos(yaw_rad)
    fwd_y = math.sin(yaw_rad)
    poses = []
    for i in range(n_frames):
        t = i / max(n_frames - 1, 1)
        px = sx + fwd_x * distance_cm * t
        py = sy + fwd_y * distance_cm * t
        pz = sz + rng.uniform(-15.0, 15.0)
        yaw = direction_deg + rng.uniform(-15.0, 15.0)
        pitch = rng.uniform(-10.0, 5.0)
        poses.append({
            "x": round(px, 2), "y": round(py, 2), "z": round(pz, 2),
            "pitch": round(pitch, 2), "yaw": round(yaw, 2), "roll": 0.0,
        })
    return poses


def _compute_trajectory_random_walk(
    start, n_frames: int = N_FRAMES, step_cm: float = 150.0,
) -> list:
    """Random walk from start — each step moves a random direction + distance.

    Produces an organic, unpredictable path through the scene. Useful for
    generating diverse viewpoints without manual waypoint placement.
    """
    import random
    rng = random.Random(42)
    sx, sy, sz = start
    px, py, pz = sx, sy, sz
    poses = []
    for i in range(n_frames):
        yaw = rng.uniform(0.0, 360.0)
        pitch = rng.uniform(-20.0, 10.0)
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


def _compute_trajectory_spline(
    center, radius: float = 500.0, n_frames: int = N_FRAMES, n_control: int = 6,
) -> list:
    """Catmull-Rom spline through random control points around center.

    Generates n_control waypoints on a hemisphere, fits a smooth Catmull-Rom
    spline, and samples n_frames evenly along the curve. Camera always looks
    toward center — produces cinematic, flowing camera motion.
    """
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
        t2 = t * t
        t3 = t2 * t
        return (
            0.5 * ((2*p1[0]) + (-p0[0]+p2[0])*t + (2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2 + (-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3),
            0.5 * ((2*p1[1]) + (-p0[1]+p2[1])*t + (2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2 + (-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3),
            0.5 * ((2*p1[2]) + (-p0[2]+p2[2])*t + (2*p0[2]-5*p1[2]+4*p2[2]-p3[2])*t2 + (-p0[2]+3*p1[2]-3*p2[2]+p3[2])*t3),
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


def _compute_trajectory_sphere_interior(
    center, radius: float = 300.0, n_frames: int = N_FRAMES,
) -> list:
    """Points on a sphere looking inward — captures walls/ceiling/floor of a room."""
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


# ═════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _get_viewport_camera(ue_editor) -> tuple:
    """Get current viewport camera position."""
    try:
        loc, rot = ue_editor.get_level_viewport_camera_info()[:2]
        return (loc.x, loc.y, loc.z)
    except Exception:
        return (0.0, 0.0, 0.0)


def _get_viewport_rotation(ue_editor) -> tuple:
    """Get current viewport camera rotation (pitch, yaw, roll) in degrees."""
    try:
        _, rot = ue_editor.get_level_viewport_camera_info()[:2]
        return (rot.pitch, rot.yaw, rot.roll)
    except Exception:
        return (0.0, 0.0, 0.0)


def _get_viewport_fov(ue_editor) -> float:
    try:
        return float(ue_editor.get_level_viewport_camera_info()[2])
    except Exception:
        return 90.0


def _euler_to_quaternion(pitch_deg, yaw_deg, roll_deg=0.0):
    """UE5 XYZ Euler → quaternion. Stdlib-only (no numpy in UE5 Python)."""
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


# ═════════════════════════════════════════════════════════════════════════════
#  FILE WRITERS
# ═════════════════════════════════════════════════════════════════════════════

def _write_camera_json(frame_dir, frame_index, pose, fov):
    data = {
        "frame_index": frame_index,
        "position": {"x": pose["x"], "y": pose["y"], "z": pose["z"]},
        "rotation_euler": {
            "pitch": pose["pitch"],
            "yaw": pose["yaw"],
            "roll": pose["roll"],
        },
        "rotation_quaternion": _euler_to_quaternion(
            pose["pitch"], pose["yaw"], pose["roll"]
        ),
        "fov": fov,
        "image_width": RESOLUTION_W,
        "image_height": RESOLUTION_H,
        "camera_convention": "ue5_x_fwd_y_right_z_up",
    }
    with open(os.path.join(frame_dir, "camera.json"), "w") as f:
        json.dump(data, f, indent=2)


def _write_objects_json(frame_dir, frame_index, actors_data):
    data = {
        "frame_index": frame_index,
        "actor_count": len(actors_data),
        "actors": actors_data,
    }
    with open(os.path.join(frame_dir, "objects.json"), "w") as f:
        json.dump(data, f, indent=2)


def _write_session_json(
    session_id,
    session_dir,
    scene_name,
    project_name,
    frame_count,
    fov,
    unique_classes,
    modality_names,
    telemetries,
):
    data = {
        "session_id": session_id,
        "scene_name": scene_name,
        "project_name": project_name,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "frame_count": frame_count,
        "config": {
            "resolution": [RESOLUTION_W, RESOLUTION_H],
            "fov_degrees": fov,
        },
        "modalities": [("depth" if m == "depth_tmp" else m) for m in modality_names],
    }
    with open(os.path.join(session_dir, "session.json"), "w") as f:
        json.dump(data, f, indent=2)


def _run_depth_post_process(session_dir: str) -> None:
    """Invoke convert_depth.py in the project venv.

    Runs after UE5 capture completes. Non-fatal on failure — the raw .hdr
    remains and the user can re-run the script manually.
    """
    if not os.path.isfile(VENV_PYTHON):
        print(
            f"[post] SKIP — project venv not found at {VENV_PYTHON}\n"
            f"       Create it:\n"
            f"         python3 -m venv .venv && "
            f"source .venv/bin/activate && pip install -r requirements.txt\n"
            f"       Or run manually:\n"
            f"         python ue5_capture/convert_depth.py {session_dir}"
        )
        return

    print(f"[post] running convert_depth.py on {session_dir}")
    try:
        result = subprocess.run(
            [VENV_PYTHON, CONVERT_DEPTH_SCRIPT, session_dir],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as e:
        print(f"[post] FAILED to invoke subprocess: {e}")
        return

    for line in result.stdout.splitlines():
        print(f"  {line}")
    if result.returncode != 0:
        print(f"[post] convert_depth.py exited with code {result.returncode}")
        for line in result.stderr.splitlines():
            print(f"  {line}")


def _clean_frames_root(frames_root):
    """Remove all frame_XXX dirs from a previous run before writing new ones."""
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


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════════

def _get_project_name() -> str:
    """Derive project name from the UE5 project descriptor (.uproject)."""
    project_dir = unreal.Paths.project_dir()
    uproject = [f for f in os.listdir(project_dir) if f.endswith(".uproject")]
    if uproject:
        return os.path.splitext(uproject[0])[0]
    return os.path.basename(project_dir.rstrip("/"))


def _get_level_name() -> str:
    """Get the current level/map name from the editor world."""
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
        name = world.get_name()
        if name.startswith("UEDPIE_"):
            name = name.split("_", 2)[-1]
        return name
    except Exception:
        return "default"


def _load_world_partition():
    """Auto-load all World Partition cells if the current level uses WP."""
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

    # Disable WP streaming first so loaded cells stay loaded
    try:
        unreal.SystemLibrary.execute_console_command(world, "wp.Runtime.EnableStreaming 0")
        print("[wp] disabled WP runtime streaming")
    except Exception as e:
        print(f"[wp] streaming disable failed: {e}")

    # Method 1: giant bounding box to capture ALL cells, not just loaded ones
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
            print("[wp] giant-bounds returned 0 descriptors, trying editor bounds...")
            raise RuntimeError("fallback")
    except Exception:
        # Method 2: fallback to editor world bounds
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
            else:
                print("[wp] no WP actor descriptors found")
        except Exception as e:
            print(f"[wp] auto-load failed: {e}")
            print(f"[wp]   manual fallback: Window > World Partition > Ctrl+A > Load Selected Cells")

    # Wait for streaming to finish
    time.sleep(2.0)
    final = len(editor_actor.get_all_level_actors())
    print(f"[wp] final actor count: {final}")


def run_capture():
    project_name = _get_project_name()
    level_name = _get_level_name()
    folder_name = f"{level_name}_{CAPTURE_LABEL}" if CAPTURE_LABEL else level_name
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

    _load_world_partition()

    # Subsystem handles (replace deprecated EditorLevelLibrary).
    ue_editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    editor_actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    if CAPTURE_MODE == "look_around":
        scene_center = _get_viewport_camera(ue_editor)
        trajectory = _compute_trajectory_look_around(scene_center, N_FRAMES)
        mode_label = "look-around (360)"
    elif CAPTURE_MODE == "multi_look":
        scene_center = _get_viewport_camera(ue_editor)
        spread = globals().get("CAPTURE_SPREAD", 200.0)
        n_stops = globals().get("CAPTURE_STOPS", 4)
        trajectory = _compute_trajectory_multi_look(scene_center, N_FRAMES, spread, n_stops)
        mode_label = f"multi-look ({n_stops} stops, spread={spread:.0f}cm)"
    elif CAPTURE_MODE == "walk_through":
        scene_center = _get_viewport_camera(ue_editor)
        _, vp_yaw, _ = _get_viewport_rotation(ue_editor)
        walk_dist = globals().get("CAPTURE_WALK_DISTANCE", 800.0)
        trajectory = _compute_trajectory_walk_through(scene_center, vp_yaw, N_FRAMES, walk_dist)
        mode_label = f"walk-through ({walk_dist:.0f}cm fwd)"
    elif CAPTURE_MODE == "sphere_interior":
        scene_center = _get_viewport_camera(ue_editor)
        trajectory = _compute_trajectory_sphere_interior(scene_center, LOCAL_ORBIT_RADIUS, N_FRAMES)
        mode_label = f"sphere-interior (r={LOCAL_ORBIT_RADIUS:.0f}cm)"
    elif CAPTURE_MODE == "local_orbit":
        scene_center = _get_viewport_camera(ue_editor)
        trajectory = _compute_trajectory(scene_center, LOCAL_ORBIT_RADIUS, N_FRAMES)
        mode_label = f"local-orbit (r={LOCAL_ORBIT_RADIUS:.0f}cm)"
    elif CAPTURE_MODE == "random_walk":
        scene_center = _get_viewport_camera(ue_editor)
        step = globals().get("CAPTURE_STEP_CM", 150.0)
        trajectory = _compute_trajectory_random_walk(scene_center, N_FRAMES, step)
        mode_label = f"random-walk (step={step:.0f}cm)"
    elif CAPTURE_MODE == "spline":
        scene_center = _get_viewport_camera(ue_editor)
        spline_r = globals().get("CAPTURE_SPLINE_RADIUS", LOCAL_ORBIT_RADIUS)
        n_ctrl = globals().get("CAPTURE_SPLINE_POINTS", 6)
        trajectory = _compute_trajectory_spline(scene_center, spline_r, N_FRAMES, n_ctrl)
        mode_label = f"spline (r={spline_r:.0f}cm, {n_ctrl} control pts)"
    else:
        scene_center, orbit_radius = _compute_scene_bounds(editor_actor)
        trajectory = _compute_trajectory(scene_center, orbit_radius, N_FRAMES)
        mode_label = f"orbit (r={orbit_radius:.0f}cm)"

    print(f"\n{'═' * 60}")
    print(f"Backlot Capture Engine")
    print(f"  Session : {session_id}")
    print(f"  Project : {project_name}")
    print(f"  Level   : {folder_name}")
    print(f"  Mode    : {mode_label}")
    print(f"  Center  : ({scene_center[0]:.0f}, {scene_center[1]:.0f}, {scene_center[2]:.0f})")
    print(f"  Frames  : {len(trajectory)}")
    print(f"  Output  : {session_dir}")
    print(f"{'═' * 60}\n")

    fov = _get_viewport_fov(ue_editor)

    rig = CaptureRig(
        width=RESOLUTION_W,
        height=RESOLUTION_H,
        fov=fov,
        modalities=NATIVE_MODALITIES,
        indirect_light_boost=INDIRECT_LIGHT_BOOST,
        exposure_bias=EXPOSURE_BIAS,
    )

    # Warmup: move to the first pose and fire throwaway captures so World
    # Partition cells finish streaming and Lumen GI accumulates initial
    # indirect lighting state.  Without this the first real frame is dark.
    first = trajectory[0]
    warmup_loc = unreal.Vector(first["x"], first["y"], first["z"])
    warmup_rot = make_rotator(first["pitch"], first["yaw"], first["roll"])
    rig.move_to(warmup_loc, warmup_rot)
    ue_editor.set_level_viewport_camera_info(warmup_loc, warmup_rot)
    WARMUP_FRAMES = 5
    for wi in range(WARMUP_FRAMES):
        rig.capture_all()
        time.sleep(0.5)
    print(f"[warmup] {WARMUP_FRAMES} throwaway captures done — WP + Lumen primed")

    telemetries = []
    unique_classes: set = set()
    try:
        for i, pose in enumerate(trajectory):
            frame_dir = os.path.join(frames_root, f"frame_{i:03d}")
            os.makedirs(frame_dir, exist_ok=True)

            tel = FrameTelemetry(frame_index=i)
            sw = Stopwatch()

            loc = unreal.Vector(pose["x"], pose["y"], pose["z"])
            rot = make_rotator(pose["pitch"], pose["yaw"], pose["roll"])
            rig.move_to(loc, rot)
            ue_editor.set_level_viewport_camera_info(loc, rot)

            tel.capture_ms = rig.capture_all()
            sw.lap_ms()

            tel.modalities_ok = rig.export_all(frame_dir)
            tel.export_ms = sw.lap_ms()

            _write_camera_json(frame_dir, i, pose, fov)
            projector = PinholeProjector(pose, RESOLUTION_W, RESOLUTION_H, fov)
            all_actors = collect_actors(editor_actor, projector, _EFFECTIVE_SKIP, _EFFECTIVE_PREFIXES)
            visible_actors = [a for a in all_actors if "bbox_2d" in a]
            _write_objects_json(frame_dir, i, visible_actors)
            tel.annotate_ms = sw.lap_ms()
            unique_classes.update(a["class"] for a in visible_actors)

            print(
                f"[frame {i:03d}] pose=({pose['x']:.0f},{pose['y']:.0f},{pose['z']:.0f}) "
                f"pitch={pose['pitch']:+.1f} yaw={pose['yaw']:+.1f} | "
                f"exp={tel.export_ms:.0f}ms ann={tel.annotate_ms:.0f}ms "
                f"visible={len(visible_actors)}/{len(all_actors)}"
            )
            telemetries.append(tel)

        _write_session_json(
            session_id,
            session_dir=session_dir,
            scene_name=folder_name,
            project_name=project_name,
            frame_count=len(trajectory),
            fov=fov,
            unique_classes=unique_classes,
            modality_names=rig.modality_names,
            telemetries=telemetries,
        )

        total_export = sum(t.export_ms for t in telemetries)
        total_annotate = sum(t.annotate_ms for t in telemetries)
        print(f"\n{'═' * 60}")
        print(
            f"Capture Complete — {len(trajectory)} frames × "
            f"{len(rig.modality_names)} modalities"
        )
        print(
            f"  total: export={total_export/1000:.1f}s "
            f"annotate={total_annotate/1000:.1f}s  "
            f"unique_classes={len(unique_classes)}"
        )
        print(f"{'═' * 60}\n")
    finally:
        rig.cleanup()
        # Re-enable WP streaming if it was disabled
        try:
            world = unreal.EditorLevelLibrary.get_editor_world()
            unreal.SystemLibrary.execute_console_command(world, "wp.Runtime.EnableStreaming 1")
        except Exception:
            pass

    _run_depth_post_process(session_dir)
    _run_ingestion(session_dir)


def _run_ingestion(session_dir: str) -> None:
    if not os.path.isfile(VENV_PYTHON):
        print(f"[ingest] SKIP — venv not found. Run manually:\n"
              f"         python -m ingestion.ingest {session_dir}")
        return

    print(f"[ingest] auto-ingesting {session_dir}")
    try:
        result = subprocess.run(
            [VENV_PYTHON, "-m", "ingestion.ingest", session_dir],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=_PROJECT_ROOT,
        )
    except Exception as e:
        print(f"[ingest] FAILED: {e}")
        return

    for line in result.stdout.splitlines():
        print(f"  {line}")
    if result.returncode != 0:
        print(f"[ingest] exited with code {result.returncode}")
        for line in result.stderr.splitlines():
            print(f"  {line}")


run_capture()
