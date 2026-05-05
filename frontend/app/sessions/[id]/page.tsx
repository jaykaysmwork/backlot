import Link from "next/link";
import { notFound } from "next/navigation";
import { getSessionById, listFrames } from "@/lib/api";
import { FadeUp, Stagger, StaggerItem, TIMING } from "@/components/motion";
import TrajectoryViewer3D from "@/components/TrajectoryViewer3D";
import ClassCatalog from "@/components/ClassCatalog";

export default async function SessionOverviewPage(
  props: { params: Promise<{ id: string }> },
) {
  const { id } = await props.params;

  const [session, frames] = await Promise.all([
    getSessionById(id).catch(() => null),
    listFrames({ session_id: id }),
  ]);

  if (!session) notFound();

  const captured = new Date(session.captured_at);
  const capturedRelative = relativeTime(captured);

  return (
    <div className="space-y-10 pb-6">
      <section className="relative isolate pt-2 pb-8">
        <div
          aria-hidden
          className="absolute inset-x-0 -top-12 h-64 -z-10 opacity-80 pointer-events-none"
          style={{ background: "var(--grad-hero)" }}
        />
        <FadeUp delay={TIMING.heroIn}>
          <nav className="flex items-center gap-2 text-[11px] font-mono text-[color:var(--text-3)]">
            <Link href="/" className="hover:text-[color:var(--text-1)]">projects</Link>
            <span className="text-[color:var(--text-muted)]">/</span>
            <Link
              href={`/projects/${encodeURIComponent(session.project_name ?? session.scene_name)}`}
              className="hover:text-[color:var(--text-1)]"
            >
              {session.project_name ?? session.scene_name}
            </Link>
            <span className="text-[color:var(--text-muted)]">/</span>
            <span className="text-[color:var(--text-2)]">session</span>
          </nav>
        </FadeUp>
        <FadeUp delay={TIMING.heroIn + 0.04}>
          <h1 className="mt-2 text-5xl md:text-6xl font-semibold tracking-tight text-[color:var(--text-1)]">
            {session.scene_name}
          </h1>
        </FadeUp>
        <FadeUp delay={TIMING.heroIn + 0.1}>
          <div className="mt-3 flex items-center gap-3 text-[11px] font-mono text-[color:var(--text-3)]">
            <span className="break-all">{session.id}</span>
            <span className="text-[color:var(--text-muted)]">·</span>
            <span>
              captured <span className="text-[color:var(--text-2)]">{capturedRelative}</span>
            </span>
          </div>
        </FadeUp>
      </section>

      <Stagger delay={TIMING.kpiIn} gap={TIMING.kpiStagger} className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StaggerItem>
          <Stat label="Frames" value={session.frame_count} detail="captured poses" />
        </StaggerItem>
        <StaggerItem>
          <Stat label="Unique Classes" value={session.unique_class_count} detail="actor types across scene" accent="#4ade80" />
        </StaggerItem>
        <StaggerItem>
          <Stat label="Modalities" value={session.modalities?.length ?? 0} detail={(session.modalities ?? []).join(" · ")} accent="#a78bfa" />
        </StaggerItem>
        <StaggerItem>
          <Stat
            label="Resolution"
            value={
              session.resolution_w && session.resolution_h
                ? `${session.resolution_w}×${session.resolution_h}`
                : "—"
            }
            detail={session.fov_degrees != null ? `fov ${session.fov_degrees.toFixed(0)}°` : undefined}
            accent="#fbbf24"
          />
        </StaggerItem>
      </Stagger>

      <section className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-4">
        <FadeUp delay={TIMING.sectionIn}>
          <TrajectoryViewer3D frames={frames.frames} sessionId={id} />
        </FadeUp>

        <FadeUp delay={TIMING.sectionIn + 0.06}>
          <div className="h-full rounded-xl border border-[color:var(--border-subtle)] bg-[color:var(--bg-1)] p-5">
            <div className="text-[10px] uppercase tracking-[0.2em] text-[color:var(--text-3)]">
              Capture Rig
            </div>
            <div className="mt-1 text-sm text-[color:var(--text-2)]">
              Synchronous SceneCapture2D · multi-modal
            </div>
            <div className="mt-5 space-y-3">
              {(session.modalities ?? []).map((m) => (
                <ModalityRow key={m} name={m} />
              ))}
            </div>
            <div className="mt-6 pt-5 border-t border-[color:var(--border-subtle)] text-[11px] font-mono text-[color:var(--text-muted)] space-y-1">
              <div className="flex justify-between">
                <span>coord</span>
                <span className="text-[color:var(--text-3)]">UE5 LH Z-up</span>
              </div>
              <div className="flex justify-between">
                <span>units</span>
                <span className="text-[color:var(--text-3)]">cm</span>
              </div>
            </div>
          </div>
        </FadeUp>
      </section>

      <FadeUp delay={TIMING.gridIn}>
        <ClassCatalog classes={session.unique_classes} sessionId={id} />
      </FadeUp>

      <FadeUp delay={TIMING.gridIn + 0.1}>
        <div className="flex justify-center pt-4">
          <Link
            href={`/sessions/${session.id}/frames`}
            className="group inline-flex items-center gap-2 rounded-full bg-[color:var(--accent)] hover:bg-[#7cb4f8] px-6 py-3 text-sm font-medium text-[#0a0a0a] shadow-[0_0_30px_var(--accent-glow)] transition"
          >
            Explore all {session.frame_count} frames
            <span className="transition-transform group-hover:translate-x-0.5">→</span>
          </Link>
        </div>
      </FadeUp>
    </div>
  );
}

function Stat({ label, value, detail, accent = "#60a5fa" }: { label: string; value: React.ReactNode; detail?: string; accent?: string }) {
  return (
    <div className="group relative rounded-xl border border-[color:var(--border-subtle)] bg-[color:var(--bg-1)] p-5 hover:border-[color:var(--border-strong)] transition overflow-hidden">
      <div aria-hidden className="absolute -top-px -right-px h-16 w-16 opacity-0 group-hover:opacity-100 transition pointer-events-none" style={{ background: `radial-gradient(circle at top right, ${accent}22, transparent 60%)` }} />
      <div className="flex items-center gap-2">
        <span className="block w-1 h-1 rounded-full" style={{ backgroundColor: accent }} />
        <div className="text-[10px] uppercase tracking-[0.2em] text-[color:var(--text-3)]">{label}</div>
      </div>
      <div className="mt-3 text-3xl font-semibold tracking-tight text-[color:var(--text-1)] tabular">{value}</div>
      {detail && <div className="mt-2 text-[11px] font-mono text-[color:var(--text-3)] truncate">{detail}</div>}
    </div>
  );
}

function ModalityRow({ name }: { name: string }) {
  const glyphs: Record<string, string> = { rgb: "RGB", depth: "Z", depth_tmp: "Z", normal: "N", base_color: "BC" };
  const colors: Record<string, string> = { rgb: "#60a5fa", depth: "#f472b6", depth_tmp: "#f472b6", normal: "#4ade80", base_color: "#fbbf24" };
  const formats: Record<string, string> = { rgb: "PNG · 8-bit", depth: "EXR → grayscale PNG", depth_tmp: "EXR → grayscale PNG", normal: "EXR → PNG", base_color: "EXR → PNG" };
  const glyph = glyphs[name] ?? name.slice(0, 2).toUpperCase();
  const color = colors[name] ?? "#94a3b8";
  return (
    <div className="flex items-center gap-3 text-sm">
      <div className="h-7 w-7 rounded-md grid place-items-center text-[10px] font-mono" style={{ background: `${color}16`, border: `1px solid ${color}30`, color }}>{glyph}</div>
      <div className="flex-1 font-mono text-[12px] text-[color:var(--text-2)]">{name}</div>
      <div className="text-[11px] text-[color:var(--text-muted)]">{formats[name] ?? ""}</div>
    </div>
  );
}

function relativeTime(d: Date): string {
  const diff = Date.now() - d.getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d ago`;
  return d.toLocaleDateString();
}
