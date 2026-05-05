"""Post-capture format conversion: float EXR modalities → web-ready PNG.

Runs in the SYSTEM Python environment (not UE5's embedded Python). UE5 drops
four float render targets (all EXR) that browsers cannot display natively —
this script keeps the float originals as ML ground truth and emits 8-bit PNG:

  depth_tmp.exr  →  depth.exr (float16, raw cm)     +  depth.png (grayscale)
  normal.exr     →  kept as-is (float32 [-1, 1])    +  normal.png (RGB vis)
  base_color.exr →  kept as-is (float32 [0, 1])     +  base_color.png (sRGB)

Usage:
    python convert_depth.py <path>
        <path> can be a single frame dir OR a session dir (contains
        frames/frame_XXX/).
    --far-cap <cm>   Clamp depth to this max for PNG normalization (default 10000 = 100m).
    --keep-src       Keep depth_tmp.exr after conversion (default: delete).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List

# OpenCV's OpenEXR support is off by default; must enable before importing cv2.
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"

import cv2  # noqa: E402
import numpy as np  # noqa: E402


SRC_NAME = "depth_tmp.exr"
PNG_NAME = "depth.png"
EXR_NAME = "depth.exr"


_SOURCE_FILES = (SRC_NAME, "normal.exr", "base_color.exr", "objects.json")


def _has_source(d: Path) -> bool:
    return any((d / name).is_file() for name in _SOURCE_FILES)


def find_frame_dirs(root: Path) -> List[Path]:
    """Return every directory under ``root`` with at least one convertible source."""
    if _has_source(root):
        return [root]
    frames_dir = root / "frames"
    if frames_dir.is_dir():
        return sorted(d for d in frames_dir.iterdir() if d.is_dir() and _has_source(d))
    return sorted(d for d in root.iterdir() if d.is_dir() and _has_source(d))


def _convert_depth(frame_dir: Path, far_cap_cm: float, keep_src: bool) -> dict | None:
    """depth_tmp.exr → depth.exr (float16) + depth.png (grayscale). No-op if absent."""
    src_path = frame_dir / SRC_NAME
    if not src_path.is_file():
        return None

    raw = cv2.imread(str(src_path), cv2.IMREAD_ANYDEPTH | cv2.IMREAD_UNCHANGED)
    if raw is None:
        raise RuntimeError(f"cv2 could not read {src_path}")

    # UE packs scene depth in R; cv2 returns BGR, so depth lives in channel 2.
    depth_cm = raw[:, :, 2] if raw.ndim == 3 else raw
    depth_cm = depth_cm.astype(np.float32)

    # EXR: raw cm, float16 (half) for ML pipelines.
    cv2.imwrite(
        str(frame_dir / EXR_NAME),
        depth_cm,
        [cv2.IMWRITE_EXR_TYPE, cv2.IMWRITE_EXR_TYPE_HALF],
    )

    # PNG: adaptive normalization — mask out sky/infinity pixels (depth ≥ far_cap)
    # so only actual scene geometry drives the percentile range.
    scene_mask = (depth_cm > 0) & (depth_cm < far_cap_cm)
    if scene_mask.any():
        p98 = float(np.percentile(depth_cm[scene_mask], 98))
    else:
        p98 = far_cap_cm
    effective_max = min(p98 * 1.1, far_cap_cm)
    clipped = np.clip(depth_cm, 0.0, effective_max)
    normalized = (clipped / effective_max * 255.0).astype(np.uint8)
    cv2.imwrite(str(frame_dir / PNG_NAME), normalized)

    if not keep_src:
        src_path.unlink()

    return {
        "min_cm": float(depth_cm.min()),
        "max_cm": float(depth_cm.max()),
        "mean_cm": float(depth_cm.mean()),
        "clipped_pct": float((depth_cm > far_cap_cm).mean() * 100.0),
    }


def _convert_normal(frame_dir: Path) -> bool:
    """normal.exr (float [-1, 1]) → normal.png (RGB, remapped to [0, 255]).

    UE stores world-space normals as signed floats. Visualization convention
    is ``n * 0.5 + 0.5`` — +X→red, +Y→green, +Z→blue. Alpha channel dropped.
    Returns True if a PNG was written.
    """
    exr_path = frame_dir / "normal.exr"
    if not exr_path.is_file():
        return False
    arr = cv2.imread(str(exr_path), cv2.IMREAD_UNCHANGED)
    if arr is None:
        return False
    if arr.ndim == 3 and arr.shape[2] >= 3:
        bgr = arr[:, :, :3]
    else:
        return False
    vis = np.clip((bgr * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
    cv2.imwrite(str(frame_dir / "normal.png"), vis)
    return True


def _convert_base_color(frame_dir: Path) -> bool:
    """base_color.exr (float [0, 1] linear) → base_color.png (sRGB 8-bit).

    UE base_color is linear. Apply a standard sRGB-ish gamma (1/2.2) so the
    PNG looks correct on a typical monitor. Returns True if a PNG was written.
    """
    exr_path = frame_dir / "base_color.exr"
    if not exr_path.is_file():
        return False
    arr = cv2.imread(str(exr_path), cv2.IMREAD_UNCHANGED)
    if arr is None:
        return False
    if arr.ndim == 3 and arr.shape[2] >= 3:
        bgr = arr[:, :, :3]
    else:
        return False
    vis = np.clip(np.power(np.clip(bgr, 0.0, 1.0), 1.0 / 2.2) * 255.0, 0, 255).astype(np.uint8)
    cv2.imwrite(str(frame_dir / "base_color.png"), vis)
    return True


def convert_one(frame_dir: Path, far_cap_cm: float, keep_src: bool) -> dict:
    """Run every conversion that applies to this frame dir."""
    depth_stats = _convert_depth(frame_dir, far_cap_cm, keep_src)
    did_normal = _convert_normal(frame_dir)
    did_base = _convert_base_color(frame_dir)
    return {
        "frame": frame_dir.name,
        "depth": depth_stats,
        "normal_png": did_normal,
        "base_color_png": did_base,
    }


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path, help="frame dir or session dir")
    parser.add_argument("--far-cap", type=float, default=10000.0, help="PNG normalization cap in cm (default 10000)")
    parser.add_argument("--keep-src", action="store_true", help="keep depth_tmp.exr after conversion")
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"[convert_depth] path not found: {args.path}", file=sys.stderr)
        return 2

    frames = find_frame_dirs(args.path)
    if not frames:
        print(
            f"[convert_depth] no convertible sources found under {args.path}",
            file=sys.stderr,
        )
        return 1

    print(f"[convert_depth] processing {len(frames)} frame(s) from {args.path}")
    for fdir in frames:
        stats = convert_one(fdir, args.far_cap, args.keep_src)
        parts = [stats["frame"]]
        d = stats["depth"]
        if d is not None:
            parts.append(
                f"depth min={d['min_cm']:.0f}cm max={d['max_cm']:.0f}cm "
                f"mean={d['mean_cm']:.0f}cm clipped={d['clipped_pct']:.1f}%"
            )
        extras = []
        if stats["normal_png"]:
            extras.append("normal.png")
        if stats["base_color_png"]:
            extras.append("base_color.png")
        if extras:
            parts.append(f"wrote {'+'.join(extras)}")
        print("  " + " | ".join(parts))
    print(f"[convert_depth] done")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
