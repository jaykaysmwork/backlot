"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { useMemo, useState } from "react";
import type { FrameSummary } from "@/lib/types";

/* ─────────────────────────────────────────────────────────
 * TRAJECTORY MAP (top-down)
 *
 *   Renders every frame's camera position as a dot on a
 *   top-down (X/Y) plot; yaw draws a subtle facing arc. The
 *   sequence is colored along a cool→warm gradient so a
 *   single glance conveys capture order + spatial spread.
 *
 *     0ms   viewport fades in
 *   120ms   axes draw on
 *   260ms   dots stagger into place (30ms each)
 *   850ms   path polyline draws
 * ───────────────────────────────────────────────────────── */

const PAD = 24;
const W = 640;
const H = 360;

type Props = {
  frames: FrameSummary[];
  /** current frame index to highlight (optional) */
  activeIndex?: number;
};

function gradientColor(t: number) {
  // cool (#60a5fa) → warm (#f472b6) across [0, 1]
  const c1 = [96, 165, 250];
  const c2 = [244, 114, 182];
  const mix = c1.map((a, i) => Math.round(a + (c2[i] - a) * t));
  return `rgb(${mix[0]}, ${mix[1]}, ${mix[2]})`;
}

export default function TrajectoryMap({ frames, activeIndex }: Props) {
  const [hover, setHover] = useState<number | null>(null);

  const { dots, pathD, xLabel, yLabel } = useMemo(() => {
    if (frames.length === 0)
      return { dots: [], pathD: "", xLabel: "", yLabel: "" };
    const xs = frames.map((f) => f.camera.x);
    const ys = frames.map((f) => f.camera.y);
    const xMin = Math.min(...xs),
      xMax = Math.max(...xs);
    const yMin = Math.min(...ys),
      yMax = Math.max(...ys);
    const xSpan = Math.max(xMax - xMin, 1);
    const ySpan = Math.max(yMax - yMin, 1);
    // keep aspect — use the larger span
    const span = Math.max(xSpan, ySpan) * 1.1;
    const cx = (xMin + xMax) / 2;
    const cy = (yMin + yMax) / 2;

    const sx = (W - PAD * 2) / span;
    const sy = (H - PAD * 2) / span;

    const dots = frames.map((f, i) => {
      const px = (f.camera.x - cx) * sx + W / 2;
      const py = (f.camera.y - cy) * sy + H / 2;
      const t = frames.length > 1 ? i / (frames.length - 1) : 0;
      return { id: f.id, index: f.frame_index, x: px, y: py, t, yaw: f.camera.yaw };
    });

    const pathD = dots.map((d, i) => `${i === 0 ? "M" : "L"}${d.x},${d.y}`).join(" ");

    return {
      dots,
      pathD,
      xLabel: `X ${Math.round(xMin)} ⟶ ${Math.round(xMax)} cm`,
      yLabel: `Y ${Math.round(yMin)} ⟶ ${Math.round(yMax)} cm`,
    };
  }, [frames]);

  if (frames.length === 0) {
    return (
      <div className="aspect-[16/9] rounded-xl border border-[color:var(--border-subtle)] bg-[color:var(--bg-1)] grid place-items-center text-sm text-[color:var(--text-3)]">
        No camera trajectory data
      </div>
    );
  }

  return (
    <div className="relative rounded-xl border border-[color:var(--border-subtle)] bg-[color:var(--bg-1)] overflow-hidden">
      <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_center,rgba(96,165,250,0.06),transparent_60%)]" />

      <div className="relative p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-[color:var(--text-3)]">
              Top-down trajectory
            </div>
            <div className="text-sm text-[color:var(--text-2)] mt-0.5">
              {frames.length} camera poses
            </div>
          </div>
          <div className="text-[10px] text-[color:var(--text-muted)] font-mono flex items-center gap-4">
            <span>
              <span className="inline-block w-2 h-2 rounded-full bg-[#60a5fa] mr-1.5 align-middle" />
              start
            </span>
            <span>
              <span className="inline-block w-2 h-2 rounded-full bg-[#f472b6] mr-1.5 align-middle" />
              end
            </span>
          </div>
        </div>

        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full h-auto"
          role="img"
          aria-label="Top-down camera trajectory plot"
        >
          {/* grid */}
          <defs>
            <pattern
              id="grid"
              x="0"
              y="0"
              width="40"
              height="40"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M 40 0 L 0 0 0 40"
                fill="none"
                stroke="rgba(255,255,255,0.03)"
                strokeWidth="1"
              />
            </pattern>
          </defs>
          <rect
            x={PAD}
            y={PAD}
            width={W - PAD * 2}
            height={H - PAD * 2}
            fill="url(#grid)"
          />

          {/* center crosshair */}
          <line
            x1={W / 2}
            y1={PAD}
            x2={W / 2}
            y2={H - PAD}
            stroke="rgba(255,255,255,0.05)"
            strokeDasharray="2 4"
          />
          <line
            x1={PAD}
            y1={H / 2}
            x2={W - PAD}
            y2={H / 2}
            stroke="rgba(255,255,255,0.05)"
            strokeDasharray="2 4"
          />

          {/* path */}
          <motion.path
            d={pathD}
            fill="none"
            stroke="rgba(96,165,250,0.35)"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: 0.9, delay: 0.85, ease: "easeInOut" }}
          />

          {/* dots */}
          {dots.map((d, i) => {
            const isActive = activeIndex === d.index;
            const isHover = hover === d.index;
            const r = isActive ? 6 : isHover ? 5 : 3.5;
            return (
              <motion.g
                key={d.id}
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{
                  type: "spring",
                  stiffness: 400,
                  damping: 22,
                  delay: 0.26 + i * 0.03,
                }}
                style={{ transformOrigin: `${d.x}px ${d.y}px` }}
                onMouseEnter={() => setHover(d.index)}
                onMouseLeave={() => setHover(null)}
                className="cursor-pointer"
              >
                <circle cx={d.x} cy={d.y} r={r + 6} fill={gradientColor(d.t)} opacity={isActive || isHover ? 0.22 : 0} />
                <circle
                  cx={d.x}
                  cy={d.y}
                  r={r}
                  fill={gradientColor(d.t)}
                  stroke="var(--bg-1)"
                  strokeWidth="1.5"
                />
                {/* yaw tick */}
                <line
                  x1={d.x}
                  y1={d.y}
                  x2={d.x + Math.cos((d.yaw * Math.PI) / 180) * 12}
                  y2={d.y + Math.sin((d.yaw * Math.PI) / 180) * 12}
                  stroke={gradientColor(d.t)}
                  strokeWidth="1.2"
                  opacity={isHover || isActive ? 0.9 : 0.45}
                />
                {/* hover label + linkable */}
                {(isHover || isActive) && (
                  <g>
                    <rect
                      x={d.x + 10}
                      y={d.y - 14}
                      width="48"
                      height="20"
                      rx="4"
                      fill="var(--bg-0)"
                      stroke={gradientColor(d.t)}
                    />
                    <text
                      x={d.x + 34}
                      y={d.y + 0}
                      textAnchor="middle"
                      fontFamily="ui-monospace, monospace"
                      fontSize="11"
                      fill="var(--text-1)"
                    >
                      #{String(d.index).padStart(3, "0")}
                    </text>
                  </g>
                )}
              </motion.g>
            );
          })}
        </svg>

        <div className="mt-3 flex items-center justify-between text-[10px] font-mono text-[color:var(--text-muted)]">
          <span>{xLabel}</span>
          <span>{yLabel}</span>
        </div>

        {/* invisible overlay of clickable links matching each dot */}
        <div className="absolute inset-0">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-full" preserveAspectRatio="xMidYMid meet">
            {dots.map((d) => (
              <Link key={d.id} href={`/frames/${d.id}`}>
                <circle
                  cx={d.x}
                  cy={d.y}
                  r={14}
                  fill="transparent"
                  style={{ cursor: "pointer" }}
                  onMouseEnter={() => setHover(d.index)}
                  onMouseLeave={() => setHover(null)}
                />
              </Link>
            ))}
          </svg>
        </div>
      </div>
    </div>
  );
}
