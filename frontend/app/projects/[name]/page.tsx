import Link from "next/link";
import { listSessions, imageUrl } from "@/lib/api";
import { FadeUp, Stagger, StaggerItem, TIMING } from "@/components/motion";
import SessionCardDelete from "@/components/SessionCardDelete";

export default async function ProjectSessionsPage(
  props: { params: Promise<{ name: string }> },
) {
  const { name } = await props.params;
  const projectName = decodeURIComponent(name);
  const sessions = await listSessions(projectName);

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
            <span className="text-[color:var(--text-2)]">{projectName}</span>
          </nav>
        </FadeUp>
        <FadeUp delay={TIMING.heroIn + 0.04}>
          <h1 className="mt-2 text-5xl md:text-6xl font-semibold tracking-tight text-[color:var(--text-1)]">
            {projectName}
          </h1>
        </FadeUp>
        <FadeUp delay={TIMING.heroIn + 0.1}>
          <p className="mt-3 text-[13px] text-[color:var(--text-3)]">
            {sessions.length} capture session{sessions.length !== 1 ? "s" : ""}
          </p>
        </FadeUp>
      </section>

      {sessions.length === 0 ? (
        <FadeUp delay={TIMING.kpiIn}>
          <div className="rounded-xl border border-dashed border-[color:var(--border-strong)] bg-[color:var(--bg-1)]/50 p-12 text-center">
            <div className="text-sm text-[color:var(--text-2)]">
              No sessions for this project yet.
            </div>
          </div>
        </FadeUp>
      ) : (
        <Stagger delay={TIMING.kpiIn} gap={0.06} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {sessions.map((s) => {
            const captured = new Date(s.captured_at);
            return (
              <StaggerItem key={s.id}>
                <Link
                  href={`/sessions/${s.id}`}
                  className="group block rounded-xl border border-[color:var(--border-subtle)] bg-[color:var(--bg-1)] overflow-hidden hover:border-[color:var(--accent)] transition"
                >
                  {s.thumbnail && (
                    <div className="relative aspect-video bg-[color:var(--bg-2)] overflow-hidden">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={imageUrl(s.thumbnail)}
                        alt={s.scene_name}
                        className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                        loading="lazy"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
                    </div>
                  )}
                  <div className="p-6">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h2 className="text-base font-semibold tracking-tight text-[color:var(--text-1)] group-hover:text-[color:var(--accent)] transition">
                          {s.scene_name}
                        </h2>
                        <div className="mt-1 text-[11px] font-mono text-[color:var(--text-muted)]">
                          {s.id.slice(0, 8)}… · {relativeTime(captured)}
                        </div>
                      </div>
                      <span className="flex items-center gap-2">
                        <SessionCardDelete sessionId={s.id} />
                        <span className="text-[color:var(--text-3)] group-hover:text-[color:var(--accent)] transition text-lg">
                          →
                        </span>
                      </span>
                    </div>

                    <div className="mt-4 grid grid-cols-3 gap-3">
                      <KV label="Frames" value={String(s.frame_count)} />
                      <KV label="Classes" value={String(s.unique_class_count)} />
                      <KV
                        label="Resolution"
                        value={
                          s.resolution_w && s.resolution_h
                            ? `${s.resolution_w}×${s.resolution_h}`
                            : "—"
                        }
                      />
                    </div>

                    {s.modalities && s.modalities.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {s.modalities.map((m) => (
                          <span
                            key={m}
                            className="rounded-md bg-[color:var(--bg-2)] border border-[color:var(--border-subtle)] px-2 py-0.5 text-[10px] font-mono text-[color:var(--text-3)]"
                          >
                            {m}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </Link>
              </StaggerItem>
            );
          })}
        </Stagger>
      )}
    </div>
  );
}

function KV({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-lg font-semibold tabular text-[color:var(--text-1)]">{value}</div>
      <div className="text-[10px] uppercase tracking-wider text-[color:var(--text-3)]">{label}</div>
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
