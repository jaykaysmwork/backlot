import Link from "next/link";
import FilterRail from "@/components/FilterRail";
import FrameCard from "@/components/FrameCard";
import { FadeUp, TIMING } from "@/components/motion";
import { listSessions, listFrames, framesNear } from "@/lib/api";

export default async function FramesPage(props: PageProps<"/frames">) {
  const sp = await props.searchParams;

  const filterParams = new URLSearchParams();
  for (const [k, v] of Object.entries(sp)) {
    if (typeof v === "string" && v.length > 0) filterParams.set(k, v);
  }

  const hasSpatial = sp.near_x && sp.near_y && sp.near_z;

  const [sessions, frames] = await Promise.all([
    listSessions(),
    hasSpatial
      ? framesNear({
          x: Number(sp.near_x),
          y: Number(sp.near_y),
          z: Number(sp.near_z),
          radius_cm: Number(sp.near_radius ?? 500),
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

  const allClasses = [...new Set(sessions.flatMap((s) => s.unique_classes))].sort();
  const totalFrameCount = sessions.reduce((sum, s) => sum + s.frame_count, 0);

  const filterQs = new URLSearchParams();
  for (const [k, v] of Object.entries(sp)) {
    if (typeof v === "string" && v.length > 0) filterQs.set(k, v);
  }
  const filterQuery = filterQs.toString();

  const activeFilters = summarizeFilters(sp);

  return (
    <div className="space-y-6">
      <FadeUp delay={TIMING.heroIn}>
        <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-3 pb-4 border-b border-[color:var(--border-subtle)]">
          <div>
            <nav className="flex items-center gap-2 text-[11px] font-mono text-[color:var(--text-3)]">
              <Link href="/" className="hover:text-[color:var(--text-1)]">
                projects
              </Link>
              <span className="text-[color:var(--text-muted)]">/</span>
              <span className="text-[color:var(--text-2)]">all frames</span>
            </nav>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight">
              Frame Browser
            </h1>
          </div>

          <div className="flex items-baseline gap-3 text-sm">
            <span className="font-mono text-3xl tabular text-[color:var(--text-1)]">
              {frames.total}
            </span>
            <span className="text-[color:var(--text-3)]">
              / {totalFrameCount} frames across {sessions.length} session{sessions.length !== 1 ? "s" : ""}
            </span>
          </div>
        </header>
      </FadeUp>

      {activeFilters.length > 0 && (
        <FadeUp delay={TIMING.heroIn + 0.05}>
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono">
            <span className="text-[color:var(--text-3)]">filters</span>
            {activeFilters.map((f) => (
              <span
                key={f}
                className="rounded-md bg-[color:var(--bg-2)] border border-[color:var(--border-subtle)] px-2 py-0.5 text-[color:var(--text-2)]"
              >
                {f}
              </span>
            ))}
            <Link
              href="/frames"
              className="text-[color:var(--text-3)] hover:text-[color:var(--accent)] underline underline-offset-2"
            >
              clear
            </Link>
          </div>
        </FadeUp>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
        <FadeUp delay={TIMING.kpiIn}>
          <FilterRail allClasses={allClasses} />
        </FadeUp>

        <section>
          {frames.frames.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[color:var(--border-strong)] bg-[color:var(--bg-1)]/50 p-12 text-center">
              <div className="inline-grid place-items-center h-12 w-12 rounded-full bg-[color:var(--bg-2)] border border-[color:var(--border-subtle)] mb-4 text-[color:var(--text-3)]">
                ⊘
              </div>
              <div className="text-sm text-[color:var(--text-2)]">
                No frames match the current filters.
              </div>
              <Link
                href="/frames"
                className="mt-3 inline-block text-[11px] text-[color:var(--accent)] hover:underline"
              >
                clear filters →
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
              {frames.frames.map((f, i) => (
                <FrameCard key={f.id} frame={f} index={i} filterQuery={filterQuery} />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function summarizeFilters(sp: Record<string, string | string[] | undefined>): string[] {
  const out: string[] = [];
  const cf = sp.class_filter;
  if (typeof cf === "string" && cf) {
    const cls = cf.split(",");
    out.push(cls.length === 1 ? `class: ${cls[0]}` : `classes: ${cls.length}`);
  }
  (["x", "y", "z"] as const).forEach((axis) => {
    const lo = sp[`${axis}_min`];
    const hi = sp[`${axis}_max`];
    if (typeof lo === "string" || typeof hi === "string") {
      out.push(
        `${axis}: ${typeof lo === "string" ? lo : "−∞"} … ${typeof hi === "string" ? hi : "+∞"}`,
      );
    }
  });
  if (sp.visible_only === "false") out.push("visible_only: false");
  if (typeof sp.near_x === "string" && typeof sp.near_y === "string" && typeof sp.near_z === "string") {
    const r = typeof sp.near_radius === "string" ? sp.near_radius : "500";
    out.push(`near: (${sp.near_x}, ${sp.near_y}, ${sp.near_z}) r=${r}cm`);
  }
  return out;
}
