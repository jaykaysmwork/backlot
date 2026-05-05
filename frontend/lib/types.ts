export type CameraPose = {
  x: number;
  y: number;
  z: number;
  pitch: number;
  yaw: number;
  roll: number;
  qx?: number | null;
  qy?: number | null;
  qz?: number | null;
  qw?: number | null;
};

export type BBox2D = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type SceneObject = {
  id: number;
  class_name: string;
  name?: string | null;
  position_x: number;
  position_y: number;
  position_z: number;
  bbox_2d?: BBox2D | null;
  visible: boolean;
};

export type FrameSummary = {
  id: string;
  frame_index: number;
  rgb_path: string;
  depth_path?: string | null;
  camera: CameraPose;
  actor_count: number;
  visible_count: number;
};

export type FrameDetail = {
  id: string;
  session_id: string;
  frame_index: number;
  rgb_path: string;
  depth_path?: string | null;
  normal_path?: string | null;
  base_color_path?: string | null;
  camera: CameraPose;
  fov_degrees?: number | null;
  resolution_w?: number | null;
  resolution_h?: number | null;
  objects: SceneObject[];
};

export type SessionOut = {
  id: string;
  scene_name: string;
  project_name?: string | null;
  captured_at: string;
  frame_count: number;
  unique_classes: string[];
  unique_class_count: number;
  modalities?: string[] | null;
  fov_degrees?: number | null;
  resolution_w?: number | null;
  resolution_h?: number | null;
  thumbnail?: string | null;
};

export type FramesList = {
  total: number;
  frames: FrameSummary[];
};

export type ProjectOut = {
  project_name: string;
  session_count: number;
  total_frames: number;
  last_captured: string | null;
  thumbnail?: string | null;
};
