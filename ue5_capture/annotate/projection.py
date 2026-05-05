"""Camera math — UE5 pose → 2D pixel projection, AABB → 2D bbox.

Pure stdlib — no ``unreal`` import, no numpy. Makes this module unit-testable
outside the editor. Convention: UE5 left-handed, +X forward, +Y right, +Z up.
Camera local axes match world axes under zero rotation.

Pinhole model: square pixels, principal point at image center, horizontal FOV.
Near-plane culling only; corners behind the camera are dropped, which can
slightly under-estimate bboxes for actors that straddle the camera. Actors
fully visible are pixel-accurate.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple


Vec3 = Tuple[float, float, float]


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def rotator_basis(pitch_deg: float, yaw_deg: float, roll_deg: float):
    """Return ``(forward, right, up)`` unit vectors in world frame for a UE5 Rotator.

    UE5 Rotator composition order: yaw * pitch * roll (intrinsic ZYX). Columns
    of the resulting matrix are the local +X, +Y, +Z axes expressed in world.
    """
    p = math.radians(pitch_deg)
    y = math.radians(yaw_deg)
    r = math.radians(roll_deg)
    cp, sp = math.cos(p), math.sin(p)
    cy, sy = math.cos(y), math.sin(y)
    cr, sr = math.cos(r), math.sin(r)

    forward: Vec3 = (cp * cy, cp * sy, sp)
    right: Vec3 = (sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp)
    up: Vec3 = (-(cr * sp * cy + sr * sy), sr * cy - cr * sp * sy, cr * cp)
    return forward, right, up


class PinholeProjector:
    """World → 2D pixel projector built from a UE5 pose + camera intrinsics.

    Parameters
    ----------
    pose : dict with x,y,z,pitch,yaw,roll (degrees, centimeters)
    image_w, image_h : pixel resolution of the target render
    fov_deg : horizontal FOV in degrees (matches SceneCaptureComponent2D.fov_angle)
    near_cm : minimum forward distance; points closer are treated as behind
    """

    def __init__(
        self,
        pose: dict,
        image_w: int,
        image_h: int,
        fov_deg: float,
        near_cm: float = 1.0,
    ) -> None:
        self.cam_pos: Vec3 = (pose["x"], pose["y"], pose["z"])
        self.w = image_w
        self.h = image_h
        self.focal_px = image_w / (2.0 * math.tan(math.radians(fov_deg) / 2.0))
        self.cx = image_w / 2.0
        self.cy = image_h / 2.0
        self.near_cm = near_cm
        self.fwd, self.right, self.up = rotator_basis(
            pose["pitch"], pose["yaw"], pose.get("roll", 0.0)
        )

    def world_to_camera(self, pt: Vec3) -> Vec3:
        """World point → camera-space ``(x_fwd, y_right, z_up)`` in cm."""
        d = (pt[0] - self.cam_pos[0], pt[1] - self.cam_pos[1], pt[2] - self.cam_pos[2])
        return (_dot(d, self.fwd), _dot(d, self.right), _dot(d, self.up))

    def project(self, pt: Vec3) -> Optional[Tuple[float, float, float]]:
        """World point → ``(pixel_x, pixel_y, depth_cm)`` or ``None`` if behind near-plane."""
        x_fwd, y_right, z_up = self.world_to_camera(pt)
        if x_fwd < self.near_cm:
            return None
        px = self.cx + (y_right / x_fwd) * self.focal_px
        py = self.cy - (z_up / x_fwd) * self.focal_px  # screen-y grows downward
        return (px, py, x_fwd)

    def _clip_edge(self, a: Vec3, b: Vec3) -> Optional[Vec3]:
        """If edge a→b crosses the near plane, return the intersection point."""
        ca = self.world_to_camera(a)
        cb = self.world_to_camera(b)
        da, db = ca[0], cb[0]
        if (da >= self.near_cm) == (db >= self.near_cm):
            return None
        t = (self.near_cm - da) / (db - da)
        return (
            a[0] + t * (b[0] - a[0]),
            a[1] + t * (b[1] - a[1]),
            a[2] + t * (b[2] - a[2]),
        )

    def project_aabb(self, origin: Vec3, extent: Vec3) -> Optional[dict]:
        """Project an axis-aligned 3D bounding box to a 2D image bbox.

        Takes ``origin`` (world-space AABB center) and ``extent`` (half-size on
        each axis). Returns a dict with clipped pixel coordinates, or ``None``
        if every corner is behind the camera or the clipped bbox has zero area.

        When the AABB straddles the near plane, edges that cross it are clipped
        and the intersection points are projected alongside the visible corners.
        """
        ox, oy, oz = origin
        ex, ey, ez = extent
        corners = [
            (ox + sx * ex, oy + sy * ey, oz + sz * ez)
            for sx in (-1, 1)
            for sy in (-1, 1)
            for sz in (-1, 1)
        ]

        # Classify corners as in-front / behind.
        front = []
        behind = []
        for c in corners:
            cam = self.world_to_camera(c)
            if cam[0] >= self.near_cm:
                front.append(c)
            else:
                behind.append(c)

        if not front:
            return None

        # Collect points to project: visible corners + near-plane edge clips.
        points_to_project = list(front)
        if behind:
            # 12 edges of an AABB: pairs sharing 2 axes, differing on 1.
            edges = []
            for i in range(8):
                for j in range(i + 1, 8):
                    diff = sum(1 for k in range(3) if corners[i][k] != corners[j][k])
                    if diff == 1:
                        edges.append((corners[i], corners[j]))
            for a, b in edges:
                clip = self._clip_edge(a, b)
                if clip is not None:
                    points_to_project.append(clip)

        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        min_depth = float("inf")
        any_visible = False

        for pt in points_to_project:
            projected = self.project(pt)
            if projected is None:
                continue
            any_visible = True
            px, py, depth = projected
            if px < min_x:
                min_x = px
            if px > max_x:
                max_x = px
            if py < min_y:
                min_y = py
            if py > max_y:
                max_y = py
            if depth < min_depth:
                min_depth = depth

        if not any_visible:
            return None

        # Clip bbox to image rectangle.
        x0 = max(0.0, min(float(self.w), min_x))
        y0 = max(0.0, min(float(self.h), min_y))
        x1 = max(0.0, min(float(self.w), max_x))
        y1 = max(0.0, min(float(self.h), max_y))

        if x1 - x0 < 1.0 or y1 - y0 < 1.0:
            return None  # entirely off-screen after clipping

        return {
            "x": round(x0, 2),
            "y": round(y0, 2),
            "width": round(x1 - x0, 2),
            "height": round(y1 - y0, 2),
            "min_depth_cm": round(min_depth, 2),
        }
