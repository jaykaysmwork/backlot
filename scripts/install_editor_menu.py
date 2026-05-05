#!/usr/bin/env python3
"""Install Backlot editor menu into UE5's global startup scripts.

Run once — after this, every UE5 project opens with the Backlot menu
in the editor menu bar.

Usage:
    python scripts/install_editor_menu.py            # install
    python scripts/install_editor_menu.py --uninstall # remove
"""

from __future__ import annotations

import argparse
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MENU_SCRIPT = os.path.join(_PROJECT_ROOT, "ue5_capture", "editor_menu.py")

_INIT_TEMPLATE = '''import os
_BACKLOT = r"{project_root}"
_menu = os.path.join(_BACKLOT, "ue5_capture", "editor_menu.py")
if os.path.isfile(_menu):
    exec(open(_menu).read(), {{**globals(), "_PROJECT_ROOT": _BACKLOT}})
'''


def _get_global_python_dir() -> str:
    if sys.platform == "darwin":
        return os.path.expanduser("~/Documents/UnrealEngine/Python")
    elif sys.platform == "win32":
        return os.path.join(os.environ.get("USERPROFILE", ""), "Documents", "UnrealEngine", "Python")
    else:
        return os.path.expanduser("~/Documents/UnrealEngine/Python")


def _install(target_dir: str) -> bool:
    init_path = os.path.join(target_dir, "init_unreal.py")

    if os.path.isfile(init_path):
        with open(init_path) as f:
            content = f.read()
        if "editor_menu.py" in content:
            return False

    os.makedirs(target_dir, exist_ok=True)
    with open(init_path, "w") as f:
        f.write(_INIT_TEMPLATE.format(project_root=_PROJECT_ROOT))
    return True


def _uninstall(target_dir: str) -> bool:
    init_path = os.path.join(target_dir, "init_unreal.py")
    if not os.path.isfile(init_path):
        return False

    with open(init_path) as f:
        content = f.read()
    if "editor_menu.py" not in content:
        return False

    os.remove(init_path)
    try:
        os.rmdir(target_dir)
    except OSError:
        pass
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--uninstall", action="store_true",
        help="Remove Backlot from UE5 startup scripts",
    )
    args = parser.parse_args()

    if not os.path.isfile(_MENU_SCRIPT):
        print(f"ERROR: editor_menu.py not found at {_MENU_SCRIPT}")
        return 1

    target_dir = _get_global_python_dir()
    init_path = os.path.join(target_dir, "init_unreal.py")

    if args.uninstall:
        if _uninstall(target_dir):
            print(f"Removed: {init_path}")
            print("Restart UE5 to take effect.")
        else:
            print("Not installed (nothing to remove).")
    else:
        if _install(target_dir):
            print(f"Installed: {init_path}")
            print("Restart UE5 — 'Backlot' menu will appear in the menu bar.")
        else:
            print("Already installed (skipped).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
