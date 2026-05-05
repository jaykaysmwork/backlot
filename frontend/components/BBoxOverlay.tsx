"use client";

import { motion } from "framer-motion";
import { useMemo, useState } from "react";
import type { SceneObject } from "@/lib/types";

/* ─────────────────────────────────────────────────────────
 * BBOX OVERLAY
 *   SVG overlay on top of the RGB frame. Colors match the
 *   class legend + catalog chips. Hover reveals a class
 *   label + min-depth. Smooth stroke-draw-in on load.
 * ───────────────────────────────────────────────────────── */

type Props = {
  imgSrc: string;
  width: number;
  height: number;
  objects: SceneObject[];
  hidden?: Set<string>;
  className?: string;
};

const PALETTE = [
  "#60a5fa", "#f472b6", "#4ade80", "#fbbf24", "#a78bfa",
  "#fb7185", "#34d399", "#f59e0b", "#22d3ee", "#e879f9",
];
function colorFor(cls: string): string {
  let h = 0;
  for (let i = 0; i < cls.length; i++) h = (h * 31 + cls.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

export default function BBoxOverlay({
  imgSrc,
  width,
  height,
  objects,
  hidden = new Set(),
  className,
}: Props) {
  const [hoverId, setHoverId] = useState<number | null>(null);

  const visible = useMemo(
    () => objects.filter((o) => o.bbox_2d && !hidden.has(o.class_name)),
    [objects, hidden],
  );

  return (
    <div className={"relative inline-block bg-black overflow-hidden ring-1 ring-[color:var(--border-subtle)] rounded-2xl " + (className ?? "")}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={imgSrc} alt="rgb" className="block max-w-full max-h-full w-auto h-auto" />
      <svg
        className="absolute inset-0 w-full h-full"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
      >
        {visible.map((o, i) => {
          const b = o.bbox_2d!;
          const color = colorFor(o.class_name);
          const isHover = hoverId === o.id;
          const bx = Math.max(0, b.x);
          const by = Math.max(0, b.y);
          const bw = Math.min(b.width, width - bx);
          const bh = Math.min(b.height, height - by);
          if (bw <= 0 || bh <= 0) return null;
          const label = o.class_name;
          const labelW = label.length * 7 + 10;
          const labelH = 16;
          const ly = by > labelH + 2 ? by - labelH - 1 : by + 1;
          return (
            <motion.g
              key={o.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: Math.min(i * 0.005, 0.4), duration: 0.2 }}
              onMouseEnter={() => setHoverId(o.id)}
              onMouseLeave={() => setHoverId(null)}
              className="cursor-pointer"
            >
              <rect
                x={bx}
                y={by}
                width={bw}
                height={bh}
                fill={isHover ? `${color}22` : "transparent"}
                stroke={color}
                strokeWidth={isHover ? 2.6 : 1.4}
                vectorEffect="non-scaling-stroke"
                rx="1"
              />
              <rect
                x={bx} y={ly} width={labelW} height={labelH}
                rx={2} fill={color} opacity={isHover ? 1 : 0.85}
              />
              <text
                x={bx + 5} y={ly + 11.5}
                fontFamily="ui-monospace, monospace"
                fontSize="10" fill="#0a0a0a" fontWeight="500"
              >
                {label}
              </text>
            </motion.g>
          );
        })}
      </svg>
    </div>
  );
}
