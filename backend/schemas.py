from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class CameraPose(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    x: float
    y: float
    z: float
    pitch: float
    yaw: float
    roll: float
    qx: Optional[float] = None
    qy: Optional[float] = None
    qz: Optional[float] = None
    qw: Optional[float] = None


class BBox2D(BaseModel):
    x: float
    y: float
    width: float
    height: float


class ObjectOut(BaseModel):
    id: int
    class_name: str
    name: Optional[str] = None
    position_x: float
    position_y: float
    position_z: float
    bbox_2d: Optional[BBox2D] = None
    visible: bool = False


class FrameSummary(BaseModel):
    id: uuid.UUID
    frame_index: int
    rgb_path: str
    depth_path: Optional[str] = None
    camera: CameraPose
    actor_count: int = 0
    visible_count: int = 0


class FrameDetail(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    frame_index: int
    rgb_path: str
    depth_path: Optional[str] = None
    normal_path: Optional[str] = None
    base_color_path: Optional[str] = None
    camera: CameraPose
    fov_degrees: Optional[float] = None
    resolution_w: Optional[int] = None
    resolution_h: Optional[int] = None
    objects: List[ObjectOut]


class SessionOut(BaseModel):
    id: uuid.UUID
    scene_name: str
    project_name: Optional[str] = None
    captured_at: datetime
    frame_count: int
    unique_classes: List[str]
    unique_class_count: int
    modalities: Optional[list] = None
    fov_degrees: Optional[float] = None
    resolution_w: Optional[int] = None
    resolution_h: Optional[int] = None
    thumbnail: Optional[str] = None


class FramesList(BaseModel):
    total: int
    frames: List[FrameSummary]


class ProjectSummary(BaseModel):
    project_name: str
    session_count: int
    total_frames: int
    last_captured: str
    thumbnail: Optional[str] = None
