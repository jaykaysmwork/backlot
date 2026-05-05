"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import type { FrameSummary } from "@/lib/types";
import { imageUrl } from "@/lib/api";

/* ─────────────────────────────────────────────────────────
 * FRAME CARD (grid item)
 *   Thumbnail + compact metadata footer. Hover reveals a
 *   subtle gradient border + scale lift.
 * ───────────────────────────────────────────────────────── */

export default function FrameCard({
  frame,
  index,
  sessionId,
  filterQuery,
}: {
  frame: FrameSummary;
  index: number;
  sessionId?: string;
  filterQuery?: string;
}) {
  const stagger = Math.min(index * 0.025, 0.6);
  const base = sessionId ? `/sessions/${sessionId}/frames/${frame.id}` : `/frames/${frame.id}`;
  const href = filterQuery ? `${base}?${filterQuery}` : base;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 26, delay: stagger }}
    >
      <Link
        href={href}
        className="group relative block rounded-xl overflow-hidden border border-[color:var(--border-subtle)] hover:border-[color:var(--accent)] bg-[color:var(--bg-1)] transition"
      >
        <div className="relative aspect-video bg-[color:var(--bg-2)] overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl(frame.rgb_path)}
            alt={`frame ${frame.frame_index}`}
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
            loading="lazy"
          />
          {/* bottom gradient for metadata legibility on top of image */}
          <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-black/70 to-transparent pointer-events-none" />

          {/* index badge */}
          <div className="absolute top-2 left-2 rounded-md bg-black/60 backdrop-blur px-2 py-0.5 text-[10px] font-mono text-white tabular ring-1 ring-white/10">
            #{String(frame.frame_index).padStart(3, "0")}
          </div>

          {/* visible count pill */}
          <div className="absolute top-2 right-2 flex items-center gap-1 rounded-md bg-black/60 backdrop-blur px-2 py-0.5 text-[10px] font-mono ring-1 ring-white/10">
            <span className="w-1.5 h-1.5 rounded-full bg-[color:var(--success)]" />
            <span className="text-white tabular">{frame.visible_count}</span>
            <span className="text-white/40">/{frame.actor_count}</span>
          </div>

          {/* camera pose overlay (bottom) */}
          <div className="absolute inset-x-0 bottom-0 p-3 font-mono text-[10px] text-white/90 flex items-center justify-between">
            <span className="tabular">
              ({frame.camera.x.toFixed(0)}, {frame.camera.y.toFixed(0)}, {frame.camera.z.toFixed(0)})
            </span>
            <span className="tabular">
              p {frame.camera.pitch.toFixed(0)}° · y {frame.camera.yaw.toFixed(0)}°
            </span>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
