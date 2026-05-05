import Link from "next/link";
import { FadeUp, Stagger, StaggerItem, TIMING } from "@/components/motion";
import { imageUrl } from "@/lib/api";
import ProjectCardDelete from "@/components/ProjectCardDelete";

const API_BASE = process.env.API_BASE_SERVER ?? process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type ProjectOut = {
  project_name: string;
  session_count: number;
  total_frames: number;
  last_captured: string | null;
  thumbnail?: string | null;
};

async function fetchProjects(): Promise<ProjectOut[]> {
  const res = await fetch(`${API_BASE}/api/projects`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export default async function ProjectsPage() {
  const projects = await fetchProjects();

  return (
    <div className="space-y-10 pb-6">
      <section className="relative isolate pt-2 pb-8">
        <div
          aria-hidden
          className="absolute inset-x-0 -top-12 h-64 -z-10 opacity-80 pointer-events-none"
          style={{ background: "var(--grad-hero)" }}
        />
        <FadeUp delay={TIMING.heroIn}>
          <div className="text-[10px] tracking-[0.3em] uppercase text-[color:var(--accent)]">
            Capture Explorer
          </div>
        </FadeUp>
        <FadeUp delay={TIMING.heroIn + 0.04}>
          <h1 className="mt-2 text-5xl md:text-6xl font-semibold tracking-tight text-[color:var(--text-1)]">
            Projects
          </h1>
        </FadeUp>
        <FadeUp delay={TIMING.heroIn + 0.1}>
          <p className="mt-3 text-[13px] text-[color:var(--text-3)] max-w-lg">
            Multi-modal synthetic data captured from Unreal Engine 5 scenes.
            Select a project to browse its capture sessions.
          </p>
        </FadeUp>
      </section>

      {projects.length === 0 ? (
        <FadeUp delay={TIMING.kpiIn}>
          <div className="rounded-xl border border-dashed border-[color:var(--border-strong)] bg-[color:var(--bg-1)]/50 p-12 text-center">
            <div className="text-sm text-[color:var(--text-2)]">
              No projects yet. Run a UE5 capture and ingest data to get started.
            </div>
          </div>
        </FadeUp>
      ) : (
        <Stagger delay={TIMING.kpiIn} gap={TIMING.kpiStagger} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((p) => (
            <StaggerItem key={p.project_name}>
              <Link
                href={`/projects/${encodeURIComponent(p.project_name)}`}
                className="group block rounded-xl border border-[color:var(--border-subtle)] bg-[color:var(--bg-1)] overflow-hidden hover:border-[color:var(--accent)] transition"
              >
                {p.thumbnail && (
                  <div className="relative aspect-video bg-[color:var(--bg-2)] overflow-hidden">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={imageUrl(p.thumbnail)}
                      alt={p.project_name}
                      className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                      loading="lazy"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
                  </div>
                )}
                <div className="p-6">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-semibold tracking-tight text-[color:var(--text-1)] group-hover:text-[color:var(--accent)] transition">
                        {p.project_name}
                      </h2>
                      <div className="mt-1 text-[11px] font-mono text-[color:var(--text-muted)]">
                        {p.last_captured
                          ? `last captured ${relativeTime(new Date(p.last_captured))}`
                          : "no captures"}
                      </div>
                    </div>
                    <span className="flex items-center gap-2">
                      <ProjectCardDelete projectName={p.project_name} />
                      <span className="text-[color:var(--text-3)] group-hover:text-[color:var(--accent)] transition text-lg">
                        →
                      </span>
                    </span>
                  </div>

                  <div className="mt-5 grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-2xl font-semibold tabular text-[color:var(--text-1)]">
                        {p.session_count}
                      </div>
                      <div className="text-[10px] uppercase tracking-wider text-[color:var(--text-3)]">
                        Sessions
                      </div>
                    </div>
                    <div>
                      <div className="text-2xl font-semibold tabular text-[color:var(--text-1)]">
                        {p.total_frames}
                      </div>
                      <div className="text-[10px] uppercase tracking-wider text-[color:var(--text-3)]">
                        Frames
                      </div>
                    </div>
                  </div>
                </div>
              </Link>
            </StaggerItem>
          ))}
        </Stagger>
      )}
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
