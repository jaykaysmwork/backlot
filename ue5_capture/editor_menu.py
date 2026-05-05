"""editor_menu.py — Backlot capture menu for UE5 Editor.

Adds an "Backlot" menu to the editor's main menu bar with one-click
capture, mode selection, presets, and a config file editor.

Setup — add to your UE5 project's Content/Python/init_unreal.py:

    import os
    _BACKLOT = r"/path/to/backlot"   # ← edit this path
    exec(
        open(os.path.join(_BACKLOT, "ue5_capture", "editor_menu.py")).read(),
        {**globals(), "_PROJECT_ROOT": _BACKLOT},
    )
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import types

import unreal


# ═══════════════════════════════════════════════════════════════════════════════
#  PATH DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def _find_project_root() -> str:
    root = globals().get("_PROJECT_ROOT")
    if root and os.path.isdir(os.path.join(root, "ue5_capture")):
        return root

    try:
        candidate = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if os.path.isdir(os.path.join(candidate, "ue5_capture")):
            return candidate
    except NameError:
        pass

    env = os.environ.get("BACKLOT_ROOT")
    if env and os.path.isdir(os.path.join(env, "ue5_capture")):
        return env

    raise RuntimeError(
        "[Backlot] Cannot detect project root.\n"
        "Set _PROJECT_ROOT before exec'ing, or set BACKLOT_ROOT env var."
    )


_PROJECT_ROOT = _find_project_root()
_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "ue5_capture", "editor_config.json")

_CAPTURE_MODES = [
    "orbit", "local_orbit", "look_around", "multi_look",
    "sphere_interior", "walk_through", "random_walk", "spline",
]

_PRESETS = [
    ("Quick Test", 5),
    ("Standard", 20),
    ("High Coverage", 50),
]


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

_COMMON_KEYS = ["mode", "n_frames", "exposure_bias", "indirect_light", "label"]

_MODE_PARAMS = {
    "orbit":          {},
    "local_orbit":    {"radius_cm": 400.0},
    "look_around":    {},
    "multi_look":     {"spread_cm": 200.0, "stops": 4},
    "walk_through":   {"walk_distance_cm": 800.0},
    "sphere_interior": {"radius_cm": 400.0},
    "random_walk":    {"step_cm": 150.0},
    "spline":         {"radius_cm": 400.0, "spline_points": 6},
}

_BATCH_KEYS = ["batch_mode", "batch_frames", "batch_cluster_r", "batch_min_actors", "dry_run"]

_DEFAULTS = {
    "mode": "orbit",
    "n_frames": 20,
    "exposure_bias": 0.0,
    "indirect_light": 3.0,
    "label": None,
    "radius_cm": 400.0,
    "spread_cm": 200.0,
    "stops": 4,
    "walk_distance_cm": 800.0,
    "step_cm": 150.0,
    "spline_points": 6,
    "batch_mode": "multi_look",
    "batch_frames": 20,
    "batch_cluster_r": 800.0,
    "batch_min_actors": 3,
    "dry_run": False,
}


def _load_config() -> dict:
    if os.path.isfile(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH) as f:
                merged = dict(_DEFAULTS)
                merged.update(json.load(f))
                return merged
        except Exception:
            pass
    return dict(_DEFAULTS)


def _visible_config(cfg: dict) -> dict:
    mode = cfg.get("mode", "orbit")
    out = {k: cfg[k] for k in _COMMON_KEYS if k in cfg}
    for k, default in _MODE_PARAMS.get(mode, {}).items():
        out[k] = cfg.get(k, default)
    for k in _BATCH_KEYS:
        if k in cfg:
            out[k] = cfg[k]
    return out


def _save_config(cfg: dict) -> None:
    with open(_CONFIG_PATH, "w") as f:
        json.dump(_visible_config(cfg), f, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
#  DIALOG
# ═══════════════════════════════════════════════════════════════════════════════

def _confirm(title: str, message: str) -> bool:
    try:
        result = unreal.EditorDialog.show_message(
            title, message,
            unreal.AppMsgType.YES_NO,
            unreal.AppReturnType.YES,
        )
        return result == unreal.AppReturnType.YES
    except Exception:
        unreal.log(f"[Backlot] {message}")
        return True


# ═══════════════════════════════════════════════════════════════════════════════
#  ACTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _open_config():
    if not os.path.isfile(_CONFIG_PATH):
        _save_config(_DEFAULTS)
    if sys.platform == "darwin":
        subprocess.Popen(["open", _CONFIG_PATH])
    elif sys.platform == "win32":
        os.startfile(_CONFIG_PATH)
    else:
        subprocess.Popen(["xdg-open", _CONFIG_PATH])
    unreal.log(f"[Backlot] Config opened: {_CONFIG_PATH}")


def _run_single():
    cfg = _load_config()
    mode = cfg["mode"]
    vis = _visible_config(cfg)
    lines = [f"{k}: {v}" for k, v in vis.items() if k not in _BATCH_KEYS]
    summary = "\n".join(lines)
    if not _confirm("Backlot — Capture Single Scene", summary + "\n\nProceed?"):
        unreal.log("[Backlot] Capture cancelled")
        return

    g = dict(globals())
    g["_PROJECT_ROOT"] = _PROJECT_ROOT
    g["CAPTURE_N_FRAMES"] = cfg["n_frames"]
    g["CAPTURE_MODE"] = mode
    g["CAPTURE_LABEL"] = cfg.get("label")
    g["CAPTURE_EXPOSURE_BIAS"] = cfg.get("exposure_bias", 0.0)
    g["CAPTURE_INDIRECT_LIGHT"] = cfg.get("indirect_light", 3.0)
    g["CAPTURE_RADIUS"] = cfg.get("radius_cm", 400.0)
    g["CAPTURE_SPREAD"] = cfg.get("spread_cm", 200.0)
    g["CAPTURE_STOPS"] = cfg.get("stops", 4)
    g["CAPTURE_WALK_DISTANCE"] = cfg.get("walk_distance_cm", 800.0)
    g["CAPTURE_STEP_CM"] = cfg.get("step_cm", 150.0)
    g["CAPTURE_SPLINE_POINTS"] = cfg.get("spline_points", 6)

    script = os.path.join(_PROJECT_ROOT, "ue5_capture", "capture.py")
    exec(open(script).read(), g)


def _run_batch():
    cfg = _load_config()
    summary = (
        f"Mode per room: {cfg['batch_mode']}\n"
        f"Frames per room: {cfg['batch_frames']}\n"
        f"Cluster radius: {cfg['batch_cluster_r']} cm\n"
        f"Min actors: {cfg['batch_min_actors']}\n"
        f"Dry run: {cfg['dry_run']}"
    )
    if not _confirm("Backlot — Batch Capture", summary + "\n\nProceed?"):
        unreal.log("[Backlot] Batch capture cancelled")
        return

    g = dict(globals())
    g["_PROJECT_ROOT"] = _PROJECT_ROOT
    g["BATCH_MODE"] = cfg["batch_mode"]
    g["BATCH_N_FRAMES"] = cfg["batch_frames"]
    g["BATCH_CLUSTER_R"] = cfg["batch_cluster_r"]
    g["BATCH_MIN_ACTORS"] = cfg["batch_min_actors"]
    g["BATCH_DRY_RUN"] = cfg["dry_run"]
    g["CAPTURE_EXPOSURE_BIAS"] = cfg["exposure_bias"]
    g["CAPTURE_INDIRECT_LIGHT"] = cfg["indirect_light"]

    script = os.path.join(_PROJECT_ROOT, "ue5_capture", "capture_batch.py")
    exec(open(script).read(), g)


def _set_mode(mode: str):
    cfg = _load_config()
    cfg["mode"] = mode
    cfg["batch_mode"] = mode
    _save_config(cfg)
    unreal.log(f"[Backlot] Mode → {mode}")


def _apply_preset(name: str, n_frames: int):
    cfg = _load_config()
    cfg["n_frames"] = n_frames
    cfg["batch_frames"] = n_frames
    _save_config(cfg)
    unreal.log(f"[Backlot] Preset → {name} ({n_frames} frames)")


def _show_status():
    cfg = _load_config()
    vis = _visible_config(cfg)
    lines = [f"{k}: {v}" for k, v in vis.items()]
    msg = "\n".join(lines)
    unreal.log(f"[Backlot] Current config:\n{msg}")
    try:
        unreal.EditorDialog.show_message(
            "Backlot — Current Config", msg,
            unreal.AppMsgType.OK, unreal.AppReturnType.OK,
        )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
#  MENU REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════════

def _make_entry(name: str, label: str, command: str, tooltip: str = ""):
    entry = unreal.ToolMenuEntry(
        name=name,
        type=unreal.MultiBlockType.MENU_ENTRY,
        insert_position=unreal.ToolMenuInsert("", unreal.ToolMenuInsertType.DEFAULT),
    )
    entry.set_label(label)
    if tooltip:
        entry.set_tool_tip(tooltip)
    entry.set_string_command(
        type=unreal.ToolMenuStringCommandType.PYTHON,
        custom_type="",
        string=command,
    )
    return entry


def _register_menu():
    mod = types.ModuleType("_backlot")
    mod._version = 1
    mod.open_config = _open_config
    mod.run_single = _run_single
    mod.run_batch = _run_batch
    mod.set_mode = _set_mode
    mod.apply_preset = _apply_preset
    mod.show_status = _show_status
    sys.modules["_backlot"] = mod

    menus = unreal.ToolMenus.get()
    main_menu = menus.find_menu("LevelEditor.MainMenu")
    if not main_menu:
        unreal.log_warning("[Backlot] LevelEditor.MainMenu not found")
        return

    ol_menu = main_menu.add_sub_menu(
        owner="Backlot",
        section_name="",
        name="Backlot",
        label="Backlot",
    )

    # ── Config section ─────────────────────────────────────────
    ol_menu.add_menu_entry("Config", _make_entry(
        "ShowStatus", "Current Config",
        "import _backlot; _backlot.show_status()",
        "Show current capture settings",
    ))
    ol_menu.add_menu_entry("Config", _make_entry(
        "Configure", "Edit Config File...",
        "import _backlot; _backlot.open_config()",
        "Open editor_config.json in system editor",
    ))

    # ── Capture section ────────────────────────────────────────
    ol_menu.add_menu_entry("Capture", _make_entry(
        "CaptureSingle", "Capture Single Scene",
        "import _backlot; _backlot.run_single()",
        "Capture the current level with current settings",
    ))
    ol_menu.add_menu_entry("Capture", _make_entry(
        "CaptureBatch", "Batch Capture (auto rooms)",
        "import _backlot; _backlot.run_batch()",
        "Auto-detect rooms and capture each one",
    ))

    # ── Mode submenu ───────────────────────────────────────────
    mode_menu = ol_menu.add_sub_menu(
        owner="Backlot",
        section_name="Settings",
        name="Mode",
        label="Mode",
    )
    for m in _CAPTURE_MODES:
        mode_menu.add_menu_entry("", _make_entry(
            f"Mode_{m}", m,
            f"import _backlot; _backlot.set_mode('{m}')",
        ))

    # ── Presets submenu ────────────────────────────────────────
    preset_menu = ol_menu.add_sub_menu(
        owner="Backlot",
        section_name="Settings",
        name="Presets",
        label="Presets",
    )
    for name, frames in _PRESETS:
        preset_menu.add_menu_entry("", _make_entry(
            f"Preset_{frames}", f"{name}  ({frames} frames)",
            f"import _backlot; _backlot.apply_preset('{name}', {frames})",
        ))

    menus.refresh_all_widgets()


# ═══════════════════════════════════════════════════════════════════════════════
#  BOOTSTRAP
# ═══════════════════════════════════════════════════════════════════════════════

if not os.path.isfile(_CONFIG_PATH):
    _save_config(_DEFAULTS)

_register_menu()
unreal.log(f"[Backlot] Menu registered — project root: {_PROJECT_ROOT}")
