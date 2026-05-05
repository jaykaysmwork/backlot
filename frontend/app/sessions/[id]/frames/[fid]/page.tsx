import { notFound } from "next/navigation";
import FrameBrowser from "@/components/FrameBrowser";
import { getFrame, listFrames, framesNear } from "@/lib/api";

export default async function FrameDetailPage(
  props: {
    params: Promise<{ id: string; fid: string }>;
    searchParams: Promise<Record<string, string | string[] | undefined>>;
  },
) {
  const { id, fid } = await props.params;
  const sp = await props.searchParams;

  const filterParams: Record<string, string | undefined> = { session_id: id };
  for (const [k, v] of Object.entries(sp)) {
    if (typeof v === "string" && v.length > 0) filterParams[k] = v;
  }

  const hasSpatial = sp.near_x && sp.near_y && sp.near_z;

  const [frame, framesList] = await Promise.all([
    getFrame(fid).catch(() => null),
    hasSpatial
      ? framesNear({
          x: Number(sp.near_x),
          y: Number(sp.near_y),
          z: Number(sp.near_z),
          radius_cm: Number((sp.near_radius as string) ?? "500"),
          session_id: id,
          class_filter: typeof sp.class_filter === "string" ? sp.class_filter : undefined,
          visible_only: typeof sp.visible_only === "string" ? sp.visible_only : undefined,
          x_min: typeof sp.x_min === "string" ? sp.x_min : undefined,
          x_max: typeof sp.x_max === "string" ? sp.x_max : undefined,
          y_min: typeof sp.y_min === "string" ? sp.y_min : undefined,
          y_max: typeof sp.y_max === "string" ? sp.y_max : undefined,
          z_min: typeof sp.z_min === "string" ? sp.z_min : undefined,
          z_max: typeof sp.z_max === "string" ? sp.z_max : undefined,
        })
      : listFrames(filterParams),
  ]);

  if (!frame || frame.session_id !== id) notFound();

  const ordered = framesList.frames;
  const idx = ordered.findIndex((f) => f.id === frame.id);
  const prev = idx > 0 ? ordered[idx - 1] : null;
  const next = idx >= 0 && idx < ordered.length - 1 ? ordered[idx + 1] : null;

  const filterQs = new URLSearchParams();
  for (const [k, v] of Object.entries(sp)) {
    if (typeof v === "string" && v.length > 0) filterQs.set(k, v);
  }
  const filterQuery = filterQs.toString();

  return (
    <FrameBrowser
      frame={frame}
      allFrames={ordered}
      neighbors={{ prev, next }}
      sessionId={id}
      filterQuery={filterQuery}
    />
  );
}
