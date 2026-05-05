"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useState } from "react";
import BBoxOverlay from "./BBoxOverlay";
import Filmstrip from "./Filmstrip";
import type { FrameDetail, FrameSummary } from "@/lib/types";
import { imageUrl } from "@/lib/api";

const PALETTE = [
  "#60a5fa", "#f472b6", "#4ade80", "#fbbf24", "#a78bfa",
  "#fb7185", "#34d399", "#f59e0b", "#22d3ee", "#e879f9",
];

const INFRA_CLASSES = new Set([
  "LevelInstance", "WorldPartitionHLOD", "WorldDataLayers",
  "CameraRig_Rail", "CameraRig_Crane",
]);
function colorFor(cls: string): string {
  let h = 0;
  for (let i = 0; i < cls.length; i++) h = (h * 31 + cls.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

type ModalityInfo = {
  key: string;
  label: string;
  sub: string;
  color: string;
  path: string | null | undefined;
};

type Props = {
  frame: FrameDetail;
  allFrames: FrameSummary[];
  neighbors: { prev: FrameSummary | null; next: FrameSummary | null };
  sessionId?: string;
  filterQuery?: string;
};

export default function FrameBrowser({ frame, allFrames, neighbors, sessionId, filterQuery }: Props) {
  const router = useRouter();
  const [hiddenClasses, setHiddenClasses] = useState<Set<string>>(new Set());
  const [boxesPerTile, setBoxesPerTile] = useState<Record<string, boolean>>({
    rgb: false, depth: false, normal: false, base_color: false,
  });
  const [expanded, setExpanded] = useState<string | null>(null);

  const visibleObjects = useMemo(() => {
    const W = frame.resolution_w ?? 1920;
    const H = frame.resolution_h ?? 1080;
    const maxArea = W * H * 0.25;
    return frame.objects.filter((o) => {
      if (!o.bbox_2d) return false;
      if (INFRA_CLASSES.has(o.class_name)) return false;
      if (o.bbox_2d.width * o.bbox_2d.height > maxArea) return false;
      return true;
    });
  }, [frame.objects, frame.resolution_w, frame.resolution_h]);
  const classesInFrame = useMemo(() => {
    const s = new Set<string>();
    visibleObjects.forEach((o) => s.add(o.class_name));
    return Array.from(s).sort();
  }, [visibleObjects]);

  const activeIndex = useMemo(
    () => allFrames.findIndex((f) => f.id === frame.id),
    [allFrames, frame.id],
  );

  const toggleClass = useCallback((cls: string) => {
    setHiddenClasses((prev) => {
      const next = new Set(prev);
      if (next.has(cls)) next.delete(cls);
      else next.add(cls);
      return next;
    });
  }, []);

  const toggleBoxes = useCallback((key: string) => {
    setBoxesPerTile((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const frameHref = useCallback((frameId: string) => {
    const base = sessionId ? `/sessions/${sessionId}/frames` : "/frames";
    return filterQuery ? `${base}/${frameId}?${filterQuery}` : `${base}/${frameId}`;
  }, [sessionId, filterQuery]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      if (e.key === "Escape") { setExpanded(null); return; }
      if (e.key === "ArrowLeft" && neighbors.prev)
        router.push(frameHref(neighbors.prev.id));
      else if (e.key === "ArrowRight" && neighbors.next)
        router.push(frameHref(neighbors.next.id));
      else if (e.key === "b" || e.key === "B")
        setBoxesPerTile((prev) => {
          const allOn = Object.values(prev).every(Boolean);
          const v = !allOn;
          return Object.fromEntries(Object.keys(prev).map((k) => [k, v]));
        });
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [neighbors, router, frameHref]);

  const classColors = useMemo(() => {
    return Object.fromEntries(classesInFrame.map((c) => [c, colorFor(c)]));
  }, [classesInFrame]);

  const modalities: ModalityInfo[] = [
    { key: "rgb", label: "RGB", sub: "PNG · 8-bit", color: "#60a5fa", path: frame.rgb_path },
    { key: "depth", label: "DEPTH", sub: "grayscale", color: "#f472b6", path: frame.depth_path },
    { key: "normal", label: "NORMAL", sub: "surface", color: "#4ade80", path: frame.normal_path },
    { key: "base_color", label: "BASE", sub: "albedo", color: "#fbbf24", path: frame.base_color_path },
  ];

  const available = modalities.filter((m) => m.path);

  return (
    <div className="space-y-5 pb-6">
      {/* top nav */}
      <motion.header
        initial={{ opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="flex items-center justify-between gap-4 flex-wrap"
      >
        <nav className="flex items-center gap-2 text-[11px] font-mono text-[color:var(--text-3)]">
          {sessionId ? (
            <>
              <Link href={`/sessions/${sessionId}`} className="hover:text-[color:var(--text-1)]">session</Link>
              <span className="text-[color:var(--text-muted)]">/</span>
              <Link href={`/sessions/${sessionId}/frames`} className="hover:text-[color:var(--text-1)]">frames</Link>
            </>
          ) : (
            <>
              <Link href="/" className="hover:text-[color:var(--text-1)]">overview</Link>
              <span className="text-[color:var(--text-muted)]">/</span>
              <Link href="/frames" className="hover:text-[color:var(--text-1)]">frames</Link>
            </>
          )}
          <span className="text-[color:var(--text-muted)]">/</span>
          <span className="text-[color:var(--text-2)] tabular">
            #{String(frame.frame_index).padStart(3, "0")}
          </span>
        </nav>

        <div className="flex items-center gap-2">
          <NavBtn href={neighbors.prev ? frameHref(neighbors.prev.id) : null} dir="left" />
          <div className="px-3 py-1 rounded-md bg-[color:var(--bg-1)] border border-[color:var(--border-subtle)] text-[11px] font-mono text-[color:var(--text-2)] tabular">
            {activeIndex + 1} <span className="text-[color:var(--text-muted)]">/</span> {allFrames.length}
          </div>
          <NavBtn href={neighbors.next ? frameHref(neighbors.next.id) : null} dir="right" />
        </div>
      </motion.header>

      {/* modality grid + metadata side-by-side */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_340px] gap-5">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 260, damping: 26, delay: 0.08 }}
        >
          {/* modality tile grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {available.map((m, i) => (
              <motion.div
                key={m.key}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.08 + i * 0.04 }}
                className="relative rounded-xl overflow-hidden border border-[color:var(--border-subtle)] bg-black cursor-pointer"
                onClick={() => setExpanded(m.key)}
              >
                {/* label badge */}
                <div className="absolute top-3 left-3 z-10 flex items-center gap-2">
                  <span
                    className="rounded-md px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-white"
                    style={{ backgroundColor: `${m.color}cc` }}
                  >
                    {m.label}
                  </span>
                  <span className="text-[10px] font-mono text-white/60">{m.sub}</span>
                </div>

                {/* boxes toggle */}
                <button
                  onClick={(e) => { e.stopPropagation(); toggleBoxes(m.key); }}
                  className={
                    "absolute top-3 right-3 z-10 rounded-md bg-black/60 backdrop-blur px-2.5 py-1 text-[10px] font-mono uppercase ring-1 ring-white/10 transition " +
                    (boxesPerTile[m.key] ? "text-white" : "text-white/50")
                  }
                >
                  BOXES
                </button>

                {/* image */}
                {boxesPerTile[m.key] ? (
                  <BBoxOverlay
                    imgSrc={imageUrl(m.path!)}
                    width={frame.resolution_w ?? 1920}
                    height={frame.resolution_h ?? 1080}
                    objects={visibleObjects}
                    hidden={hiddenClasses}
                    className="w-full"
                  />
                ) : (
                  <div className="relative w-full">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={imageUrl(m.path!)}
                      alt={m.key}
                      className="block w-full h-auto"
                    />
                  </div>
                )}
              </motion.div>
            ))}
          </div>

          <div className="mt-2 text-[11px] font-mono text-[color:var(--text-muted)] text-center">
            ← / → navigate · <kbd className="font-mono">B</kbd> toggle all boxes
          </div>
        </motion.div>

        {/* metadata sidebar */}
        <motion.aside
          initial={{ opacity: 0, x: 10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ type: "spring", stiffness: 260, damping: 26, delay: 0.26 }}
          className="space-y-3"
        >
          <Panel title="Camera Pose">
            <KV label="POSITION" value={
              `${frame.camera.x.toFixed(1)},  ${frame.camera.y.toFixed(1)},  ${frame.camera.z.toFixed(1)}`
            } unit="cm" />
            <KV label="PITCH" value={frame.camera.pitch.toFixed(2)} />
            <KV label="YAW" value={frame.camera.yaw.toFixed(2)} />
            <KV label="ROLL" value={frame.camera.roll.toFixed(2)} />
            {frame.fov_degrees != null && (
              <KV label="FOV" value={frame.fov_degrees.toFixed(1)} />
            )}
            {frame.resolution_w && frame.resolution_h && (
              <KV label="RESOLUTION" value={`${frame.resolution_w} × ${frame.resolution_h}`} unit="px" />
            )}
          </Panel>

          <Panel
            title="Classes"
            trailing={
              <span className="text-[10px] font-mono text-[color:var(--text-muted)] tabular">
                {classesInFrame.length - hiddenClasses.size}/{classesInFrame.length}
              </span>
            }
          >
            <div className="max-h-[220px] overflow-y-auto pr-1 space-y-0.5">
              {classesInFrame.map((cls) => {
                const hidden = hiddenClasses.has(cls);
                const count = visibleObjects.filter((o) => o.class_name === cls).length;
                return (
                  <button
                    key={cls}
                    onClick={() => toggleClass(cls)}
                    className={
                      "w-full flex items-center gap-2 rounded px-1.5 py-1 text-[11px] font-mono text-left transition " +
                      (hidden
                        ? "text-[color:var(--text-muted)] hover:text-[color:var(--text-2)]"
                        : "text-[color:var(--text-2)] hover:bg-[color:var(--bg-2)]")
                    }
                  >
                    <span
                      className="inline-block w-2 h-2 rounded-sm shrink-0"
                      style={{
                        backgroundColor: hidden ? "transparent" : classColors[cls],
                        border: hidden ? `1px solid ${classColors[cls]}` : "none",
                      }}
                    />
                    <span className="flex-1 truncate">{cls}</span>
                    <span className="text-[10px] text-[color:var(--text-muted)] tabular">×{count}</span>
                  </button>
                );
              })}
            </div>
          </Panel>

          <Panel
            title="Objects"
            trailing={
              <span className="text-[10px] font-mono text-[color:var(--text-muted)] tabular">
                {visibleObjects.length}/{frame.objects.length}
              </span>
            }
          >
            <div className="max-h-[300px] overflow-y-auto pr-1 space-y-0.5 text-[11px] font-mono">
              {visibleObjects.map((o) => (
                <div
                  key={o.id}
                  className="flex items-center justify-between gap-2 px-1.5 py-1 rounded hover:bg-[color:var(--bg-2)]"
                >
                  <span className="flex items-center gap-1.5 min-w-0">
                    <span
                      className="inline-block w-1.5 h-1.5 rounded-sm shrink-0"
                      style={{ backgroundColor: classColors[o.class_name] ?? "#888" }}
                    />
                    <span className="truncate text-[color:var(--text-2)]" title={o.class_name}>
                      {o.class_name}
                    </span>
                  </span>
                  {o.name && (
                    <span className="text-[color:var(--text-muted)] tabular shrink-0 truncate max-w-[100px]" title={o.name}>
                      {o.name}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </Panel>
        </motion.aside>
      </div>

      {/* filmstrip */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 220, damping: 26, delay: 0.36 }}
      >
        <Filmstrip frames={allFrames} activeIndex={activeIndex} sessionId={sessionId} filterQuery={filterQuery} />
      </motion.div>

      <div className="text-[11px] font-mono text-[color:var(--text-muted)] text-center">
        ← / → navigate · click a tile to expand · <kbd className="font-mono">B</kbd> toggle all boxes
      </div>

      {/* lightbox */}
      {expanded && (() => {
        const m = available.find((mod) => mod.key === expanded);
        if (!m) return null;
        return (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
            onClick={() => setExpanded(null)}
          >
            <div className="relative max-w-[95vw] max-h-[95vh]" onClick={(e) => e.stopPropagation()}>
              <div className="absolute top-3 left-3 z-10 flex items-center gap-2">
                <span
                  className="rounded-md px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-white"
                  style={{ backgroundColor: `${m.color}cc` }}
                >
                  {m.label}
                </span>
                <span className="text-[10px] font-mono text-white/60">{m.sub}</span>
              </div>
              <div className="absolute top-3 right-3 z-10 flex items-center gap-2">
                <button
                  onClick={() => setBoxesPerTile((prev) => ({ ...prev, [m.key]: !prev[m.key] }))}
                  className={
                    "rounded-md bg-black/60 backdrop-blur px-2.5 py-1 text-[11px] font-mono uppercase ring-1 ring-white/10 hover:ring-white/30 transition " +
                    (boxesPerTile[m.key] ? "text-white" : "text-white/50")
                  }
                >
                  BOXES
                </button>
                <button
                  onClick={() => setExpanded(null)}
                  className="rounded-md bg-black/60 backdrop-blur px-2.5 py-1 text-[11px] font-mono text-white ring-1 ring-white/10 hover:ring-white/30 transition"
                >
                  ESC
                </button>
              </div>
              <div className="relative">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={imageUrl(m.path!)}
                  alt={m.key}
                  className="max-w-[95vw] max-h-[95vh] object-contain rounded-xl"
                />
                {boxesPerTile[m.key] && (
                  <svg
                    className="absolute inset-0 w-full h-full rounded-xl"
                    viewBox={`0 0 ${frame.resolution_w ?? 1920} ${frame.resolution_h ?? 1080}`}
                    preserveAspectRatio="xMidYMid meet"
                  >
                    {(() => {
                      const W = frame.resolution_w ?? 1920;
                      const H = frame.resolution_h ?? 1080;
                      return visibleObjects
                        .filter((o) => !hiddenClasses.has(o.class_name))
                        .map((o) => {
                          const b = o.bbox_2d!;
                          const color = colorFor(o.class_name);
                          const bx = Math.max(0, b.x);
                          const by = Math.max(0, b.y);
                          const bw = Math.min(b.width, W - bx);
                          const bh = Math.min(b.height, H - by);
                          if (bw <= 0 || bh <= 0) return null;
                          const label = o.class_name;
                          const labelW = label.length * 7 + 10;
                          const labelH = 16;
                          const ly = by > labelH + 2 ? by - labelH - 1 : by + 1;
                          return (
                            <g key={o.id}>
                              <rect
                                x={bx} y={by} width={bw} height={bh}
                                fill="transparent" stroke={color} strokeWidth={1.4}
                                vectorEffect="non-scaling-stroke" rx="1"
                              />
                              <rect
                                x={bx} y={ly} width={labelW} height={labelH}
                                rx={2} fill={color} opacity={0.9}
                              />
                              <text
                                x={bx + 5} y={ly + 11.5}
                                fontFamily="ui-monospace, monospace"
                                fontSize="10" fill="#0a0a0a" fontWeight="500"
                              >
                                {label}
                              </text>
                            </g>
                          );
                        });
                    })()}
                  </svg>
                )}
              </div>
            </div>
          </motion.div>
        );
      })()}
    </div>
  );
}

function Panel({
  title,
  trailing,
  children,
}: {
  title: string;
  trailing?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-[color:var(--border-subtle)] bg-[color:var(--bg-1)]">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[color:var(--border-subtle)]">
        <div className="text-[10px] uppercase tracking-[0.2em] text-[color:var(--text-3)]">
          {title}
        </div>
        {trailing}
      </div>
      <div className="p-3">{children}</div>
    </div>
  );
}

function KV({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 text-[11px] font-mono">
      <span className="text-[color:var(--text-3)]">{label}</span>
      <span className="text-[color:var(--text-1)] tabular">
        {value}
        {unit && <span className="text-[color:var(--text-muted)] ml-1 text-[10px]">{unit}</span>}
      </span>
    </div>
  );
}

function NavBtn({ href, dir }: { href: string | null; dir: "left" | "right" }) {
  const cls =
    "h-7 w-7 grid place-items-center rounded-md border text-sm transition " +
    (href
      ? "border-[color:var(--border-subtle)] hover:border-[color:var(--accent)] hover:text-[color:var(--accent)] text-[color:var(--text-2)]"
      : "border-[color:var(--border-subtle)]/50 text-[color:var(--text-muted)] pointer-events-none");
  const arrow = dir === "left" ? "←" : "→";
  return href ? (
    <Link href={href} className={cls}>{arrow}</Link>
  ) : (
    <span className={cls}>{arrow}</span>
  );
}
