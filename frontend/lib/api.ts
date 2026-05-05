import type { FrameDetail, FramesList, ProjectOut, SessionOut } from "./types";

const API_BASE_BROWSER =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const API_BASE_SERVER =
  process.env.API_BASE_SERVER ?? API_BASE_BROWSER;

function apiBase(): string {
  return typeof window === "undefined" ? API_BASE_SERVER : API_BASE_BROWSER;
}

async function fetchJson<T>(path: string): Promise<T> {
  const url = `${apiBase()}${path}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} on ${url}`);
  }
  return res.json() as Promise<T>;
}

export function getSession(): Promise<SessionOut> {
  return fetchJson<SessionOut>("/api/session");
}

export function listFrames(
  params: URLSearchParams | Record<string, string | undefined> = {},
): Promise<FramesList> {
  const sp =
    params instanceof URLSearchParams
      ? params
      : (() => {
          const u = new URLSearchParams();
          for (const [k, v] of Object.entries(params)) {
            if (v !== undefined && v !== "") u.set(k, v);
          }
          return u;
        })();
  const qs = sp.toString();
  return fetchJson<FramesList>(`/api/frames${qs ? `?${qs}` : ""}`);
}

export function getFrame(id: string): Promise<FrameDetail> {
  return fetchJson<FrameDetail>(`/api/frames/${id}`);
}

export function imageUrl(relPath: string): string {
  return `${API_BASE_BROWSER}/images/${relPath}`;
}

export function listProjects(): Promise<ProjectOut[]> {
  return fetchJson<ProjectOut[]>("/api/projects");
}

export function listSessions(projectName?: string): Promise<SessionOut[]> {
  const qs = projectName ? `?project_name=${encodeURIComponent(projectName)}` : "";
  return fetchJson<SessionOut[]>(`/api/sessions${qs}`);
}

export function getSessionById(id: string): Promise<SessionOut> {
  return fetchJson<SessionOut>(`/api/sessions/${id}`);
}

export async function deleteSession(id: string): Promise<void> {
  const res = await fetch(`${API_BASE_BROWSER}/api/sessions/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}

export async function deleteProject(name: string): Promise<void> {
  const res = await fetch(
    `${API_BASE_BROWSER}/api/projects/${encodeURIComponent(name)}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}

export function framesNear(params: {
  x: number;
  y: number;
  z: number;
  radius_cm: number;
  session_id?: string;
  class_filter?: string;
  visible_only?: string;
  x_min?: string;
  x_max?: string;
  y_min?: string;
  y_max?: string;
  z_min?: string;
  z_max?: string;
}): Promise<FramesList> {
  const sp = new URLSearchParams();
  sp.set("x", String(params.x));
  sp.set("y", String(params.y));
  sp.set("z", String(params.z));
  sp.set("radius_cm", String(params.radius_cm));
  if (params.session_id) sp.set("session_id", params.session_id);
  if (params.class_filter) sp.set("class_filter", params.class_filter);
  if (params.visible_only !== undefined) sp.set("visible_only", params.visible_only);
  for (const key of ["x_min", "x_max", "y_min", "y_max", "z_min", "z_max"] as const) {
    if (params[key] !== undefined) sp.set(key, params[key]);
  }
  return fetchJson<FramesList>(`/api/frames/near?${sp}`);
}
