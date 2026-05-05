from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session as OrmSession, selectinload

from .config import CAPTURE_OUTPUT_DIR
from .db import SessionLocal
from .models import Frame, SceneObject, Session
from .schemas import (
    BBox2D,
    CameraPose,
    FrameDetail,
    FrameSummary,
    FramesList,
    ObjectOut,
    ProjectSummary,
    SessionOut,
)


app = FastAPI(
    title="Backlot Capture Explorer",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(CAPTURE_OUTPUT_DIR, exist_ok=True)
app.mount(
    "/images",
    StaticFiles(directory=CAPTURE_OUTPUT_DIR, follow_symlink=True),
    name="images",
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _camera(frame: Frame) -> CameraPose:
    return CameraPose(
        x=frame.camera_x,
        y=frame.camera_y,
        z=frame.camera_z,
        pitch=frame.camera_pitch,
        yaw=frame.camera_yaw,
        roll=frame.camera_roll,
        qx=frame.camera_qx,
        qy=frame.camera_qy,
        qz=frame.camera_qz,
        qw=frame.camera_qw,
    )


def _object_out(obj: SceneObject) -> ObjectOut:
    bbox = None
    if obj.bbox_x is not None:
        bbox = BBox2D(
            x=obj.bbox_x,
            y=obj.bbox_y,
            width=obj.bbox_width,
            height=obj.bbox_height,
        )
    return ObjectOut(
        id=obj.id,
        class_name=obj.class_name,
        name=obj.name,
        position_x=obj.position_x,
        position_y=obj.position_y,
        position_z=obj.position_z,
        bbox_2d=bbox,
        visible=obj.visible,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/sessions")
def list_sessions(
    db: OrmSession = Depends(get_db),
    project_name: Optional[str] = Query(None),
):
    q = select(Session)
    if project_name is not None:
        project_col = func.coalesce(Session.project_name, Session.scene_name)
        q = q.where(project_col == project_name)
    q = q.order_by(Session.captured_at.desc())
    sessions = db.execute(q).scalars().all()
    result = []
    for s in sessions:
        unique_classes = [
            row[0]
            for row in db.execute(
                select(SceneObject.class_name)
                .join(Frame, Frame.id == SceneObject.frame_id)
                .where(Frame.session_id == s.id)
                .distinct()
                .order_by(SceneObject.class_name)
            ).all()
        ]
        thumb = db.execute(
            select(Frame.rgb_path)
            .where(Frame.session_id == s.id)
            .order_by(Frame.frame_index)
            .limit(1)
        ).scalar_one_or_none()
        result.append(SessionOut(
            id=s.id,
            scene_name=s.scene_name,
            project_name=s.project_name,
            captured_at=s.captured_at,
            frame_count=s.frame_count,
            unique_classes=unique_classes,
            unique_class_count=len(unique_classes),
            modalities=s.modalities,
            fov_degrees=s.fov_degrees,
            resolution_w=s.resolution_w,
            resolution_h=s.resolution_h,
            thumbnail=thumb,
        ))
    return result


@app.get("/api/session", response_model=SessionOut)
def get_session(db: OrmSession = Depends(get_db)):
    session = db.execute(
        select(Session).order_by(Session.captured_at.desc()).limit(1)
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(404, "no sessions ingested yet")

    unique_classes = [
        row[0]
        for row in db.execute(
            select(SceneObject.class_name)
            .join(Frame, Frame.id == SceneObject.frame_id)
            .where(Frame.session_id == session.id)
            .distinct()
            .order_by(SceneObject.class_name)
        ).all()
    ]

    return SessionOut(
        id=session.id,
        scene_name=session.scene_name,
        project_name=session.project_name,
        captured_at=session.captured_at,
        frame_count=session.frame_count,
        unique_classes=unique_classes,
        unique_class_count=len(unique_classes),
        modalities=session.modalities,
        fov_degrees=session.fov_degrees,
        resolution_w=session.resolution_w,
        resolution_h=session.resolution_h,
    )


@app.get("/api/projects", response_model=list[ProjectSummary])
def list_projects(db: OrmSession = Depends(get_db)):
    project_col = func.coalesce(Session.project_name, Session.scene_name)
    rows = db.execute(
        select(
            project_col.label("project_name"),
            func.count(Session.id).label("session_count"),
            func.sum(Session.frame_count).label("total_frames"),
            func.max(Session.captured_at).label("last_captured"),
        )
        .group_by(project_col)
        .order_by(func.max(Session.captured_at).desc())
    ).all()
    result = []
    for r in rows:
        thumb = db.execute(
            select(Frame.rgb_path)
            .join(Session, Session.id == Frame.session_id)
            .where(func.coalesce(Session.project_name, Session.scene_name) == r.project_name)
            .order_by(Session.captured_at.desc(), Frame.frame_index)
            .limit(1)
        ).scalar_one_or_none()
        result.append(ProjectSummary(
            project_name=r.project_name,
            session_count=r.session_count,
            total_frames=r.total_frames,
            last_captured=r.last_captured.isoformat() if r.last_captured else "",
            thumbnail=thumb,
        ))
    return result


@app.get("/api/sessions/{session_id}", response_model=SessionOut)
def get_session_by_id(session_id: uuid.UUID, db: OrmSession = Depends(get_db)):
    session = db.execute(
        select(Session).where(Session.id == session_id)
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(404, f"session {session_id} not found")

    unique_classes = [
        row[0]
        for row in db.execute(
            select(SceneObject.class_name)
            .join(Frame, Frame.id == SceneObject.frame_id)
            .where(Frame.session_id == session.id)
            .distinct()
            .order_by(SceneObject.class_name)
        ).all()
    ]

    return SessionOut(
        id=session.id,
        scene_name=session.scene_name,
        project_name=session.project_name,
        captured_at=session.captured_at,
        frame_count=session.frame_count,
        unique_classes=unique_classes,
        unique_class_count=len(unique_classes),
        modalities=session.modalities,
        fov_degrees=session.fov_degrees,
        resolution_w=session.resolution_w,
        resolution_h=session.resolution_h,
    )


def _delete_session_files(session: Session) -> str | None:
    """Remove the session's capture directory from disk."""
    import shutil
    project = session.project_name or ""
    scene = session.scene_name or ""
    session_dir = Path(CAPTURE_OUTPUT_DIR) / project / scene
    if not session_dir.is_dir():
        session_dir = Path(CAPTURE_OUTPUT_DIR) / scene
    if session_dir.is_dir():
        shutil.rmtree(session_dir, ignore_errors=True)
        return str(session_dir)
    return None


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: uuid.UUID, db: OrmSession = Depends(get_db)):
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(404, f"session {session_id} not found")
    deleted_path = _delete_session_files(session)
    db.delete(session)
    db.commit()
    return {"deleted": str(session_id), "files_removed": deleted_path}


@app.delete("/api/projects/{project_name}")
def delete_project(project_name: str, db: OrmSession = Depends(get_db)):
    import shutil

    project_col = func.coalesce(Session.project_name, Session.scene_name)
    sessions = db.execute(
        select(Session).where(project_col == project_name)
    ).scalars().all()
    if not sessions:
        raise HTTPException(404, f"project '{project_name}' not found")
    deleted_paths = []
    for s in sessions:
        p = _delete_session_files(s)
        if p:
            deleted_paths.append(p)
        db.delete(s)

    project_dir = Path(CAPTURE_OUTPUT_DIR) / project_name
    if project_dir.is_dir():
        shutil.rmtree(project_dir, ignore_errors=True)
        if str(project_dir) not in deleted_paths:
            deleted_paths.append(str(project_dir))

    db.commit()
    return {"deleted": project_name, "sessions_removed": len(sessions), "files_removed": deleted_paths}


@app.get("/api/frames", response_model=FramesList)
def list_frames(
    db: OrmSession = Depends(get_db),
    session_id: Optional[str] = None,
    class_filter: Optional[str] = Query(None),
    visible_only: bool = Query(True),
    x_min: Optional[float] = None,
    x_max: Optional[float] = None,
    y_min: Optional[float] = None,
    y_max: Optional[float] = None,
    z_min: Optional[float] = None,
    z_max: Optional[float] = None,
):
    conditions = []
    if session_id:
        conditions.append(Frame.session_id == uuid.UUID(session_id))
    if x_min is not None:
        conditions.append(Frame.camera_x >= x_min)
    if x_max is not None:
        conditions.append(Frame.camera_x <= x_max)
    if y_min is not None:
        conditions.append(Frame.camera_y >= y_min)
    if y_max is not None:
        conditions.append(Frame.camera_y <= y_max)
    if z_min is not None:
        conditions.append(Frame.camera_z >= z_min)
    if z_max is not None:
        conditions.append(Frame.camera_z <= z_max)

    q = select(Frame)
    if conditions:
        q = q.where(and_(*conditions))

    if class_filter:
        wanted = [c.strip() for c in class_filter.split(",") if c.strip()]
        for klass in wanted:
            exists_q = select(SceneObject.id).where(
                SceneObject.frame_id == Frame.id,
                SceneObject.class_name == klass,
            )
            if visible_only:
                exists_q = exists_q.where(SceneObject.visible == True)
            q = q.where(exists_q.exists())

    q = q.order_by(Frame.session_id, Frame.frame_index)
    frames = db.execute(q).scalars().all()

    frame_ids = [f.id for f in frames]
    counts: dict = {}
    if frame_ids:
        counts_rows = db.execute(
            select(
                SceneObject.frame_id,
                func.count(SceneObject.id),
                func.count(SceneObject.id).filter(SceneObject.visible == True),
            )
            .where(SceneObject.frame_id.in_(frame_ids))
            .group_by(SceneObject.frame_id)
        ).all()
        counts = {r[0]: (r[1], r[2]) for r in counts_rows}

    summaries = [
        FrameSummary(
            id=f.id,
            frame_index=f.frame_index,
            rgb_path=f.rgb_path,
            depth_path=f.depth_path,
            camera=_camera(f),
            actor_count=counts.get(f.id, (0, 0))[0],
            visible_count=counts.get(f.id, (0, 0))[1],
        )
        for f in frames
    ]
    return FramesList(total=len(summaries), frames=summaries)


@app.get("/api/classes")
def list_classes(db: OrmSession = Depends(get_db)):
    rows = db.execute(
        select(SceneObject.class_name, func.count(SceneObject.id))
        .group_by(SceneObject.class_name)
        .order_by(SceneObject.class_name)
    ).all()
    return [{"class_name": r[0], "count": r[1]} for r in rows]


@app.get("/api/frames/near", response_model=FramesList)
def frames_near(
    x: float = Query(...),
    y: float = Query(...),
    z: float = Query(...),
    radius_cm: float = Query(500.0, gt=0),
    session_id: Optional[str] = None,
    class_filter: Optional[str] = Query(None),
    visible_only: bool = Query(True),
    x_min: Optional[float] = None,
    x_max: Optional[float] = None,
    y_min: Optional[float] = None,
    y_max: Optional[float] = None,
    z_min: Optional[float] = None,
    z_max: Optional[float] = None,
    db: OrmSession = Depends(get_db),
):
    session_clause = ""
    params: dict = {"x": x, "y": y, "z": z, "radius": radius_cm}
    if session_id:
        session_clause = "AND f.session_id = :sid"
        params["sid"] = uuid.UUID(session_id)
    sql = text(f"""
        SELECT f.id
        FROM frames f
        WHERE f.geom IS NOT NULL
          AND ST_3DDWithin(
            f.geom,
            ST_MakePoint(:x, :y, :z),
            :radius
        )
        {session_clause}
        ORDER BY f.session_id, f.frame_index
    """)
    rows = db.execute(sql, params).all()
    frame_ids = [r[0] for r in rows]
    if not frame_ids:
        return FramesList(total=0, frames=[])

    q = select(Frame).where(Frame.id.in_(frame_ids))

    range_conditions = []
    if x_min is not None:
        range_conditions.append(Frame.camera_x >= x_min)
    if x_max is not None:
        range_conditions.append(Frame.camera_x <= x_max)
    if y_min is not None:
        range_conditions.append(Frame.camera_y >= y_min)
    if y_max is not None:
        range_conditions.append(Frame.camera_y <= y_max)
    if z_min is not None:
        range_conditions.append(Frame.camera_z >= z_min)
    if z_max is not None:
        range_conditions.append(Frame.camera_z <= z_max)
    if range_conditions:
        q = q.where(and_(*range_conditions))

    if class_filter:
        wanted = [c.strip() for c in class_filter.split(",") if c.strip()]
        for klass in wanted:
            exists_q = select(SceneObject.id).where(
                SceneObject.frame_id == Frame.id,
                SceneObject.class_name == klass,
            )
            if visible_only:
                exists_q = exists_q.where(SceneObject.visible == True)
            q = q.where(exists_q.exists())
    q = q.order_by(Frame.session_id, Frame.frame_index)

    frames = db.execute(q).scalars().all()
    filtered_ids = [f.id for f in frames]
    counts: dict = {}
    if filtered_ids:
        counts_rows = db.execute(
            select(
                SceneObject.frame_id,
                func.count(SceneObject.id),
                func.count(SceneObject.id).filter(SceneObject.visible == True),
            )
            .where(SceneObject.frame_id.in_(filtered_ids))
            .group_by(SceneObject.frame_id)
        ).all()
        counts = {r[0]: (r[1], r[2]) for r in counts_rows}

    summaries = [
        FrameSummary(
            id=f.id,
            frame_index=f.frame_index,
            rgb_path=f.rgb_path,
            depth_path=f.depth_path,
            camera=_camera(f),
            actor_count=counts.get(f.id, (0, 0))[0],
            visible_count=counts.get(f.id, (0, 0))[1],
        )
        for f in frames
    ]
    return FramesList(total=len(summaries), frames=summaries)


@app.get("/api/frames/{frame_id}", response_model=FrameDetail)
def get_frame(frame_id: uuid.UUID, db: OrmSession = Depends(get_db)):
    frame = db.execute(
        select(Frame)
        .options(selectinload(Frame.objects))
        .where(Frame.id == frame_id)
    ).scalar_one_or_none()
    if frame is None:
        raise HTTPException(404, f"frame {frame_id} not found")

    session = db.get(Session, frame.session_id)

    return FrameDetail(
        id=frame.id,
        session_id=frame.session_id,
        frame_index=frame.frame_index,
        rgb_path=frame.rgb_path,
        depth_path=frame.depth_path,
        normal_path=frame.normal_path,
        base_color_path=frame.base_color_path,
        camera=_camera(frame),
        fov_degrees=session.fov_degrees if session else None,
        resolution_w=session.resolution_w if session else None,
        resolution_h=session.resolution_h if session else None,
        objects=[_object_out(o) for o in frame.objects],
    )
