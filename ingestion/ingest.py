"""Ingest a capture_output/<session_id> directory into Postgres.

Reads session.json + per-frame camera.json + objects.json, writes rows to
sessions / frames / objects. Idempotent: re-running the same session UUID
updates in place; child rows are replaced to avoid orphans.

File paths in the DB are relative to CAPTURE_OUTPUT_DIR (the parent of all
session directories) so they resolve correctly through the FastAPI static mount.

Usage:
    python -m ingestion.ingest capture_output/<session_id>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session as OrmSession

from backend.config import CAPTURE_OUTPUT_DIR
from backend.db import SessionLocal, engine
from backend.models import Base, Frame, SceneObject, Session


def _get(obj: dict, *keys: str, default: Any = None) -> Any:
    cur: Any = obj
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _upsert_session(db: OrmSession, session_json: dict, session_dir: Path) -> Session:
    session_id = uuid.UUID(session_json["session_id"])
    captured_at = datetime.fromisoformat(session_json["captured_at"])

    config = session_json.get("config") or {}
    resolution = config.get("resolution") or [None, None]

    row = {
        "id": session_id,
        "scene_name": session_json["scene_name"],
        "project_name": session_json.get("project_name"),
        "captured_at": captured_at,
        "frame_count": session_json["frame_count"],
        "fov_degrees": config.get("fov_degrees"),
        "resolution_w": resolution[0] if isinstance(resolution, list) and len(resolution) > 0 else None,
        "resolution_h": resolution[1] if isinstance(resolution, list) and len(resolution) > 1 else None,
        "modalities": session_json.get("modalities"),
    }

    stmt = pg_insert(Session).values(**row)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={k: stmt.excluded[k] for k in row if k != "id"},
    )
    db.execute(stmt)
    db.flush()
    return db.get(Session, session_id)


def _ingest_frame(
    db: OrmSession,
    session_row: Session,
    session_dir: Path,
    frame_dir: Path,
) -> tuple[Frame, int]:
    camera = json.loads((frame_dir / "camera.json").read_text())

    m = re.search(r"frame_(\d+)", frame_dir.name)
    frame_index = int(m.group(1)) if m else int(frame_dir.name)

    capture_root = Path(CAPTURE_OUTPUT_DIR)
    try:
        session_prefix = session_dir.relative_to(capture_root).as_posix()
    except ValueError:
        session_prefix = session_dir.name
    frame_rel = f"{session_prefix}/frames/{frame_dir.name}"

    pos = camera["position"]
    rot = camera["rotation_euler"]
    quat = camera.get("rotation_quaternion") or {}

    def _modality_path(filename: str) -> str | None:
        if (frame_dir / filename).exists():
            return f"{frame_rel}/{filename}"
        return None

    existing = db.execute(
        select(Frame).where(
            Frame.session_id == session_row.id,
            Frame.frame_index == frame_index,
        )
    ).scalar_one_or_none()

    cx, cy, cz = float(pos["x"]), float(pos["y"]), float(pos["z"])
    values = dict(
        session_id=session_row.id,
        frame_index=frame_index,
        rgb_path=f"{frame_rel}/rgb.png",
        depth_path=_modality_path("depth.png"),
        normal_path=_modality_path("normal.png"),
        base_color_path=_modality_path("base_color.png"),
        camera_x=cx,
        camera_y=cy,
        camera_z=cz,
        camera_pitch=float(rot["pitch"]),
        camera_yaw=float(rot["yaw"]),
        camera_roll=float(rot["roll"]),
        camera_qx=quat.get("x"),
        camera_qy=quat.get("y"),
        camera_qz=quat.get("z"),
        camera_qw=quat.get("w"),
        geom=func.ST_MakePoint(cx, cy, cz),
    )

    if existing is None:
        frame = Frame(**values)
        db.add(frame)
        db.flush()
    else:
        for k, v in values.items():
            setattr(existing, k, v)
        frame = existing
        db.execute(delete(SceneObject).where(SceneObject.frame_id == frame.id))
        db.flush()

    objects_list = json.loads((frame_dir / "objects.json").read_text())
    if isinstance(objects_list, dict):
        objects_list = objects_list.get("actors") or []

    rows = []
    for a in objects_list:
        pos_obj = a.get("position") or a.get("world_position") or {}
        bbox = a.get("bbox_2d")
        rows.append(
            dict(
                frame_id=frame.id,
                class_name=a.get("class_name") or a.get("class", "Unknown"),
                name=a.get("name"),
                position_x=float(pos_obj.get("x", 0.0)),
                position_y=float(pos_obj.get("y", 0.0)),
                position_z=float(pos_obj.get("z", 0.0)),
                bbox_x=float(bbox["x"]) if bbox else None,
                bbox_y=float(bbox["y"]) if bbox else None,
                bbox_width=float(bbox["width"]) if bbox else None,
                bbox_height=float(bbox["height"]) if bbox else None,
                visible=a.get("visible", bbox is not None),
            )
        )

    BATCH = 500
    for i in range(0, len(rows), BATCH):
        db.execute(pg_insert(SceneObject).values(rows[i:i + BATCH]))

    return frame, len(rows)


def ingest(root: Path) -> dict:
    session_json = json.loads((root / "session.json").read_text())
    frames_root = root / "frames"
    frame_dirs = sorted(
        d for d in frames_root.iterdir() if d.is_dir() and (d / "camera.json").is_file()
    )
    if not frame_dirs:
        raise RuntimeError(f"no frame dirs found under {frames_root}")

    Base.metadata.create_all(engine)

    stats = {"session_id": session_json["session_id"], "frames": 0, "objects": 0, "stale_removed": 0}
    with SessionLocal() as db, db.begin():
        session_row = _upsert_session(db, session_json, root)

        ingested_indices: set[int] = set()
        for fdir in frame_dirs:
            m = re.search(r"frame_(\d+)", fdir.name)
            idx = int(m.group(1)) if m else int(fdir.name)
            ingested_indices.add(idx)
            _, n_objs = _ingest_frame(db, session_row, root, fdir)
            stats["frames"] += 1
            stats["objects"] += n_objs

        stale = db.execute(
            select(Frame).where(
                Frame.session_id == session_row.id,
                ~Frame.frame_index.in_(ingested_indices),
            )
        ).scalars().all()
        for f in stale:
            db.execute(delete(SceneObject).where(SceneObject.frame_id == f.id))
            db.delete(f)
        stats["stale_removed"] = len(stale)

    return stats


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", nargs="?", type=Path, default=None, help="capture_output/<session_id> directory (or parent to auto-discover)")
    args = parser.parse_args(argv)

    if args.path is None:
        env_dir = os.environ.get("CAPTURE_OUTPUT_DIR")
        if env_dir:
            args.path = Path(env_dir)
        else:
            print("[ingest] no path given and CAPTURE_OUTPUT_DIR not set", file=sys.stderr)
            return 2

    root = args.path.resolve()

    if (root / "session.json").exists():
        session_dirs = [root]
    else:
        # Search up to 2 levels: capture_output/<project>/<session_id>/session.json
        session_dirs = []
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            if (child / "session.json").is_file():
                session_dirs.append(child)
            else:
                for grandchild in sorted(child.iterdir()):
                    if grandchild.is_dir() and (grandchild / "session.json").is_file():
                        session_dirs.append(grandchild)
        if not session_dirs:
            print(f"[ingest] no session.json found under {root}", file=sys.stderr)
            return 2
        print(f"[ingest] found {len(session_dirs)} session(s) under {root}")

    for sd in session_dirs:
        print(f"[ingest] source={sd}")
        stats = ingest(sd)
        print(
            f"[ingest] session={stats['session_id']} "
            f"frames={stats['frames']} objects={stats['objects']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
