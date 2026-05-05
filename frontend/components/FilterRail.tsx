"use client";

/* ─────────────────────────────────────────────────────────
 * FILTER RAIL
 *   Collapsible sections, searchable class list, select-all,
 *   live apply. URL is the source of truth — form state
 *   rehydrates from searchParams so back/forward stays sane.
 * ───────────────────────────────────────────────────────── */

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

type Props = {
  allClasses: string[];
  basePath?: string;
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

export default function FilterRail({ allClasses, basePath = "/frames" }: Props) {
  const router = useRouter();
  const sp = useSearchParams();

  const initialClasses = useMemo(
    () => (sp.get("class_filter") ?? "").split(",").filter(Boolean),
    [sp],
  );

  const [selected, setSelected] = useState<Set<string>>(() => new Set(initialClasses));
  const [xMin, setXMin] = useState(sp.get("x_min") ?? "");
  const [xMax, setXMax] = useState(sp.get("x_max") ?? "");
  const [yMin, setYMin] = useState(sp.get("y_min") ?? "");
  const [yMax, setYMax] = useState(sp.get("y_max") ?? "");
  const [zMin, setZMin] = useState(sp.get("z_min") ?? "");
  const [zMax, setZMax] = useState(sp.get("z_max") ?? "");
  const [visibleOnly, setVisibleOnly] = useState(sp.get("visible_only") !== "false");
  const [search, setSearch] = useState("");
  const [nearX, setNearX] = useState(sp.get("near_x") ?? "");
  const [nearY, setNearY] = useState(sp.get("near_y") ?? "");
  const [nearZ, setNearZ] = useState(sp.get("near_z") ?? "");
  const [nearRadius, setNearRadius] = useState(sp.get("near_radius") ?? "500");

  const classMatches = useMemo(() => {
    const s = search.trim().toLowerCase();
    return s ? allClasses.filter((c) => c.toLowerCase().includes(s)) : allClasses;
  }, [search, allClasses]);

  const apply = useCallback(() => {
    const next = new URLSearchParams();
    if (selected.size > 0) next.set("class_filter", Array.from(selected).join(","));
    if (xMin) next.set("x_min", xMin);
    if (xMax) next.set("x_max", xMax);
    if (yMin) next.set("y_min", yMin);
    if (yMax) next.set("y_max", yMax);
    if (zMin) next.set("z_min", zMin);
    if (zMax) next.set("z_max", zMax);
    if (!visibleOnly) next.set("visible_only", "false");
    if (nearX && nearY && nearZ) {
      next.set("near_x", nearX);
      next.set("near_y", nearY);
      next.set("near_z", nearZ);
      next.set("near_radius", nearRadius || "500");
    }
    router.push(`${basePath}${next.toString() ? `?${next}` : ""}`);
  }, [router, selected, xMin, xMax, yMin, yMax, zMin, zMax, visibleOnly, nearX, nearY, nearZ, nearRadius, basePath]);

  const reset = useCallback(() => {
    setSelected(new Set());
    setXMin(""); setXMax(""); setYMin(""); setYMax("");
    setZMin(""); setZMax("");
    setNearX(""); setNearY(""); setNearZ(""); setNearRadius("500");
    setVisibleOnly(true);
    setSearch("");
    router.push(basePath);
  }, [router, basePath]);

  const toggleClass = (cls: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(cls)) next.delete(cls);
      else next.add(cls);
      return next;
    });

  const hasFilters =
    selected.size > 0 || xMin || xMax || yMin || yMax || zMin || zMax || !visibleOnly || (nearX && nearY && nearZ);

  return (
    <aside className="space-y-3 sticky top-20 self-start">
      <div className="rounded-xl border border-[color:var(--border-subtle)] bg-[color:var(--bg-1)] overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[color:var(--border-subtle)]">
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-[color:var(--text-3)]">Filters</div>
            <div className="text-sm text-[color:var(--text-2)] mt-0.5 tabular">
              {hasFilters ? "Active" : "None"}
            </div>
          </div>
          <button
            onClick={reset}
            disabled={!hasFilters}
            className="text-[11px] text-[color:var(--text-3)] hover:text-[color:var(--text-1)] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Reset
          </button>
        </div>

        {/* Camera Range */}
        <Section title="Camera Range" hint="cm">
          <div className="grid grid-cols-[auto_1fr_1fr] gap-1.5 items-center text-xs">
            <Axis label="X" color="#60a5fa" />
            <Input value={xMin} onChange={setXMin} placeholder="min" />
            <Input value={xMax} onChange={setXMax} placeholder="max" />
            <Axis label="Y" color="#4ade80" />
            <Input value={yMin} onChange={setYMin} placeholder="min" />
            <Input value={yMax} onChange={setYMax} placeholder="max" />
            <Axis label="Z" color="#f472b6" />
            <Input value={zMin} onChange={setZMin} placeholder="min" />
            <Input value={zMax} onChange={setZMax} placeholder="max" />
          </div>
        </Section>

        {/* Spatial Query (PostGIS) */}
        <Section title="Spatial Query" hint="PostGIS">
          <p className="text-[10px] text-[color:var(--text-muted)] mb-2 leading-snug">
            find frames within radius of a point using ST_3DDWithin
          </p>
          <div className="grid grid-cols-[auto_1fr] gap-1.5 items-center text-xs">
            <Axis label="X" color="#60a5fa" />
            <Input value={nearX} onChange={setNearX} placeholder="x" />
            <Axis label="Y" color="#4ade80" />
            <Input value={nearY} onChange={setNearY} placeholder="y" />
            <Axis label="Z" color="#f472b6" />
            <Input value={nearZ} onChange={setNearZ} placeholder="z" />
            <span className="text-[10px] font-mono text-[color:var(--text-3)]">R</span>
            <Input value={nearRadius} onChange={setNearRadius} placeholder="500" />
          </div>
        </Section>

        {/* Classes */}
        <Section
          title="Actor Classes"
          hint={`${selected.size}/${allClasses.length}`}
          right={
            selected.size > 0 ? (
              <button
                onClick={() => setSelected(new Set())}
                className="text-[10px] text-[color:var(--text-3)] hover:text-[color:var(--text-1)]"
              >
                clear
              </button>
            ) : null
          }
        >
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search classes…"
            className="mb-2 w-full rounded-md bg-[color:var(--bg-2)] border border-[color:var(--border-subtle)] focus:border-[color:var(--accent)] px-2.5 py-1.5 text-[11px] font-mono placeholder:text-[color:var(--text-muted)] outline-none"
          />
          <div className="max-h-[280px] overflow-y-auto pr-1 space-y-0.5">
            {classMatches.map((cls) => {
              const on = selected.has(cls);
              const color = colorFor(cls);
              return (
                <button
                  key={cls}
                  onClick={() => toggleClass(cls)}
                  className={
                    "w-full flex items-center gap-2 rounded-md px-2 py-1.5 text-[11px] font-mono text-left transition " +
                    (on
                      ? "bg-[color:var(--bg-3)] text-[color:var(--text-1)]"
                      : "hover:bg-[color:var(--bg-2)] text-[color:var(--text-2)]")
                  }
                >
                  <span
                    className="inline-block w-2 h-2 rounded-sm shrink-0"
                    style={{
                      backgroundColor: on ? color : "transparent",
                      border: on ? "none" : `1px solid ${color}`,
                    }}
                  />
                  <span className="flex-1 truncate">{cls}</span>
                  {on && <span className="text-[color:var(--accent)] text-[9px]">●</span>}
                </button>
              );
            })}
            {classMatches.length === 0 && (
              <div className="py-4 text-center text-[11px] text-[color:var(--text-muted)]">
                no match
              </div>
            )}
          </div>
        </Section>

        {/* Visibility */}
        <Section title="Visibility" noHint>
          <label className="flex items-start gap-2.5 text-[11px] cursor-pointer select-none">
            <input
              type="checkbox"
              checked={visibleOnly}
              onChange={(e) => setVisibleOnly(e.target.checked)}
              className="mt-0.5 accent-[color:var(--accent)]"
            />
            <span className="flex-1">
              <span className="text-[color:var(--text-2)]">Require on-screen bbox</span>
              <span className="block text-[10px] text-[color:var(--text-muted)] mt-0.5 leading-snug">
                match only frames where the class is actually visible (not behind camera or clipped)
              </span>
            </span>
          </label>
        </Section>

        <div className="p-3 border-t border-[color:var(--border-subtle)] bg-[color:var(--bg-0)]/40">
          <button
            onClick={apply}
            className="w-full rounded-md bg-[color:var(--accent)] hover:bg-[#7cb4f8] px-3 py-2 text-xs font-medium text-[#0a0a0a] transition"
          >
            Apply filters
          </button>
        </div>
      </div>
    </aside>
  );
}

function Section({
  title,
  hint,
  right,
  noHint,
  children,
}: {
  title: string;
  hint?: string;
  right?: React.ReactNode;
  noHint?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="px-4 py-4 border-b border-[color:var(--border-subtle)]">
      <div className="flex items-center justify-between mb-2.5">
        <div className="flex items-baseline gap-2">
          <h3 className="text-[11px] font-semibold tracking-wide text-[color:var(--text-1)]">
            {title}
          </h3>
          {!noHint && hint && (
            <span className="text-[10px] font-mono text-[color:var(--text-muted)]">
              {hint}
            </span>
          )}
        </div>
        {right}
      </div>
      {children}
    </div>
  );
}

function Axis({ label, color }: { label: string; color: string }) {
  return (
    <span className="flex items-center gap-1.5 text-[10px] font-mono text-[color:var(--text-3)]">
      <span className="w-1.5 h-1.5 rounded-sm" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}

function Input({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  return (
    <input
      type="number"
      step="any"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full rounded bg-[color:var(--bg-2)] border border-[color:var(--border-subtle)] focus:border-[color:var(--accent)] px-1.5 py-1 text-[10px] font-mono placeholder:text-[color:var(--text-muted)] outline-none tabular"
    />
  );
}
