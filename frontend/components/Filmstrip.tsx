"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { useEffect, useRef } from "react";
import type { FrameSummary } from "@/lib/types";
import { imageUrl } from "@/lib/api";

/* ─────────────────────────────────────────────────────────
 * FILMSTRIP
 *   Horizontal scroller of every frame in the session.
 *   Current frame is visually accented + auto-scrolled into
 *   view so navigation feels grounded in the full set.
 * ───────────────────────────────────────────────────────── */

export default function Filmstrip({
  frames,
  activeIndex,
  sessionId,
  filterQuery,
}: {
  frames: FrameSummary[];
  activeIndex: number;
  sessionId?: string;
  filterQuery?: string;
}) {
  const scrollerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollerRef.current?.querySelector<HTMLElement>(
      `[data-frame-index="${activeIndex}"]`,
    );
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
  }, [activeIndex]);

  return (
    <div className="rounded-xl border border-[color:var(--border-subtle)] bg-[color:var(--bg-1)]">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[color:var(--border-subtle)]">
        <div className="text-[10px] uppercase tracking-[0.2em] text-[color:var(--text-3)]">
          All frames
        </div>
        <div className="text-[11px] font-mono text-[color:var(--text-muted)] tabular">
          {activeIndex + 1} / {frames.length}
        </div>
      </div>
      <div
        ref={scrollerRef}
        className="flex gap-2 overflow-x-auto overflow-y-hidden p-3 scroll-smooth"
      >
        {frames.map((f, i) => {
          const active = i === activeIndex;
          return (
            <motion.div
              key={f.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(i * 0.015, 0.35), type: "spring", stiffness: 260, damping: 26 }}
            >
              <Link
                data-frame-index={i}
                href={`${sessionId ? `/sessions/${sessionId}/frames` : "/frames"}/${f.id}${filterQuery ? `?${filterQuery}` : ""}`}
                className={
                  "relative block shrink-0 rounded-md overflow-hidden border transition " +
                  (active
                    ? "border-[color:var(--accent)] ring-2 ring-[color:var(--accent-glow)]"
                    : "border-[color:var(--border-subtle)] hover:border-[color:var(--border-strong)]")
                }
                style={{ width: 112, height: 63 }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={imageUrl(f.rgb_path)}
                  alt={`frame ${i}`}
                  className="absolute inset-0 w-full h-full object-cover"
                  loading="lazy"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
                <div
                  className={
                    "absolute bottom-1 left-1.5 text-[9px] font-mono tabular " +
                    (active ? "text-white" : "text-white/80")
                  }
                >
                  #{String(f.frame_index).padStart(3, "0")}
                </div>
              </Link>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
