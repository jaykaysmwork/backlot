import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey,
    Index, Integer, String, UniqueConstraint, event, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

try:
    from geoalchemy2 import Geometry
except ImportError:
    from sqlalchemy import LargeBinary
    Geometry = lambda **kw: LargeBinary


class Base(DeclarativeBase):
    pass


@event.listens_for(Base.metadata, "before_create")
def _enable_postgis(target, connection, **kw):
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    scene_name: Mapped[str] = mapped_column(String(256), nullable=False)
    project_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    frame_count: Mapped[int] = mapped_column(Integer, nullable=False)
    fov_degrees: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resolution_w: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolution_h: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    modalities: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    frames: Mapped[List["Frame"]] = relationship(
        back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_sessions_scene_name", "scene_name"),
    )


class Frame(Base):
    __tablename__ = "frames"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)
    rgb_path: Mapped[str] = mapped_column(String(512), nullable=False)
    depth_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    normal_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    base_color_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    camera_x: Mapped[float] = mapped_column(Float, nullable=False)
    camera_y: Mapped[float] = mapped_column(Float, nullable=False)
    camera_z: Mapped[float] = mapped_column(Float, nullable=False)
    camera_pitch: Mapped[float] = mapped_column(Float, nullable=False)
    camera_yaw: Mapped[float] = mapped_column(Float, nullable=False)
    camera_roll: Mapped[float] = mapped_column(Float, nullable=False)
    camera_qx: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    camera_qy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    camera_qz: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    camera_qw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geom = Column(Geometry(geometry_type="POINTZ", srid=0), nullable=True)

    session: Mapped["Session"] = relationship(back_populates="frames")
    objects: Mapped[List["SceneObject"]] = relationship(
        back_populates="frame", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("session_id", "frame_index", name="uq_frame_session_index"),
        Index("ix_frames_session_id", "session_id"),
        Index("ix_frames_camera_z", "camera_z"),
        Index("ix_frames_geom", "geom", postgresql_using="gist"),
    )


class SceneObject(Base):
    __tablename__ = "objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    frame_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("frames.id", ondelete="CASCADE"), nullable=False)
    class_name: Mapped[str] = mapped_column(String(256), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    position_x: Mapped[float] = mapped_column(Float, nullable=False)
    position_y: Mapped[float] = mapped_column(Float, nullable=False)
    position_z: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_width: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_height: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    visible: Mapped[bool] = mapped_column(Boolean, default=False)

    frame: Mapped["Frame"] = relationship(back_populates="objects")

    __table_args__ = (
        Index("ix_objects_class_name", "class_name"),
        Index("ix_objects_frame_id", "frame_id"),
    )
