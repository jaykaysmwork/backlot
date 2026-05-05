"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { useMemo, useState } from "react";

/* ─────────────────────────────────────────────────────────
 * CLASS CATALOG
 *   Browsable, searchable grid of actor classes. Each chip
 *   is a deep-link into /frames pre-filtered by that class.
 *   Colors are derived from the same palette the bbox
 *   overlay uses, so "BP_Coin_C pink" means the same thing
 *   across the whole app.
 * ───────────────────────────────────────────────────────── */

const PALETTE = [
  "#60a5fa", "#f472b6", "#4ade80", "#fbbf24", "#a78bfa",
  "#fb7185", "#34d399", "#f59e0b", "#22d3ee", "#e879f9",
];

function colorFor(cls: string): string {
  let h = 0;
  for (let i = 0; i < cls.length; i++) h = (h * 31 + cls.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

export default function ClassCatalog({ classes, sessionId }: { classes: string[]; sessionId?: string }) {
  const [q, setQ] = useState("");
  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    return s ? classes.filter((c) => c.toLowerCase().includes(s)) : classes;
  }, [q, classes]);

  return (
    <div className="rounded-xl border border-[color:var(--border-subtle)] bg-[color:var(--bg-1)] p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-[color:var(--text-3)]">
            Class Catalog
          </div>
          <div className="text-sm text-[color:var(--text-2)] mt-0.5">
            {filtered.length}/{classes.length} classes · click to filter frames
          </div>
        </div>
        <div className="relative">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search classes…"
            className="w-48 rounded-md bg-[color:var(--bg-2)] border border-[color:var(--border-subtle)] focus:border-[color:var(--accent)] px-3 py-1.5 text-xs font-mono placeholder:text-[color:var(--text-muted)] outline-none"
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {filtered.map((cls, i) => {
          const color = colorFor(cls);
          return (
            <motion.span
              key={cls}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(i * 0.015, 0.6), type: "spring", stiffness: 400, damping: 26 }}
            >
              <Link
                href={sessionId ? `/sessions/${sessionId}/frames?class_filter=${encodeURIComponent(cls)}` : `/frames?class_filter=${encodeURIComponent(cls)}`}
                className="group inline-flex items-center gap-1.5 rounded-md border border-[color:var(--border-subtle)] hover:border-[color:var(--border-strong)] bg-[color:var(--bg-2)] hover:bg-[color:var(--bg-3)] px-2.5 py-1 text-[11px] font-mono text-[color:var(--text-2)] hover:text-[color:var(--text-1)] transition"
              >
                <span
                  className="inline-block w-2 h-2 rounded-sm group-hover:shadow-[0_0_8px_currentColor] transition"
                  style={{ backgroundColor: color, color }}
                />
                {cls}
              </Link>
            </motion.span>
          );
        })}
        {filtered.length === 0 && (
          <div className="text-xs text-[color:var(--text-3)] py-4 px-2">
            No classes match &quot;{q}&quot;.
          </div>
        )}
      </div>
    </div>
  );
}
