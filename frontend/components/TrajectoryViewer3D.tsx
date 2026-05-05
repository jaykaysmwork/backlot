"use client";

/* ─────────────────────────────────────────────────────────
 * 3D TRAJECTORY VIEWER (Three.js via React Three Fiber)
 *
 *   Renders every camera pose in the session as a dot in
 *   UE5 world space; a colored polyline threads them in
 *   capture order (cool → warm). Each dot is a link into
 *   the corresponding frame. Camera orbits, zooms, pans —
 *   standard OrbitControls.
 *
 *   UE5 coordinate convention: +X forward, +Y right, +Z up.
 *   Three.js is Y-up right-handed. We remap UE(x,y,z) →
 *   Three(x, z, -y) to keep the UE "up" feeling correct.
 *
 *   Animation storyboard:
 *     0ms    canvas fades in
 *   200ms    dots stagger into place (40ms each)
 *   900ms    trajectory line draws
 *  1400ms    scene is interactive
 * ───────────────────────────────────────────────────────── */

import { OrbitControls, Html, Line, Billboard, Grid } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import type { FrameSummary } from "@/lib/types";

type Props = {
  frames: FrameSummary[];
  activeIndex?: number;
  sessionId?: string;
};

function gradientColor(t: number): THREE.Color {
  const c1 = new THREE.Color("#60a5fa");
  const c2 = new THREE.Color("#f472b6");
  return c1.clone().lerp(c2, t);
}

/** Remap a UE5 world coord (cm) into Three's Y-up space, scaled. */
function toThree(p: { x: number; y: number; z: number }, scale: number): [number, number, number] {
  return [p.x * scale, p.z * scale, -p.y * scale];
}

export default function TrajectoryViewer3D({ frames, activeIndex, sessionId }: Props) {
  const router = useRouter();

  const { positions, colors, scale, center, size, isStationary } = useMemo(() => {
    if (frames.length === 0) {
      return {
        positions: [] as [number, number, number][],
        colors: [] as THREE.Color[],
        scale: 1,
        center: new THREE.Vector3(0, 0, 0),
        size: 10,
        isStationary: true,
      };
    }
    const xs = frames.map((f) => f.camera.x);
    const ys = frames.map((f) => f.camera.y);
    const zs = frames.map((f) => f.camera.z);
    const xMin = Math.min(...xs), xMax = Math.max(...xs);
    const yMin = Math.min(...ys), yMax = Math.max(...ys);
    const zMin = Math.min(...zs), zMax = Math.max(...zs);
    const spans = [xMax - xMin, yMax - yMin, zMax - zMin];
    const span = Math.max(...spans, 1);
    const stationary = span < 10;
    const s = 10 / span;

    const cx = (xMin + xMax) / 2;
    const cy = (yMin + yMax) / 2;
    const cz = (zMin + zMax) / 2;

    const positions = frames.map((f) =>
      toThree(
        { x: f.camera.x - cx, y: f.camera.y - cy, z: f.camera.z - cz },
        s,
      ),
    );
    const colors = frames.map((_, i) =>
      gradientColor(frames.length > 1 ? i / (frames.length - 1) : 0),
    );

    return {
      positions,
      colors,
      scale: s,
      center: new THREE.Vector3(0, 0, 0),
      size: 10,
      isStationary: stationary,
    };
  }, [frames]);

  return (
    <div className="relative rounded-xl border border-[color:var(--border-subtle)] bg-[color:var(--bg-1)] overflow-hidden">
      <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_center,rgba(96,165,250,0.06),transparent_60%)] z-0" />

      <div className="relative z-10 p-5 flex items-center justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-[color:var(--text-3)]">
            3D Trajectory
          </div>
          <div className="text-sm text-[color:var(--text-2)] mt-0.5">
            {frames.length} camera poses · drag to orbit · scroll to zoom
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

      <div className="relative z-0 h-[420px]">
        {isStationary ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-6">
            <div className="text-3xl text-[color:var(--text-muted)] mb-3">360</div>
            <div className="text-sm text-[color:var(--text-2)]">
              Fixed-position capture — camera rotates in place
            </div>
            <div className="mt-2 text-[11px] font-mono text-[color:var(--text-muted)]">
              ({frames[0]?.camera.x.toFixed(0)}, {frames[0]?.camera.y.toFixed(0)}, {frames[0]?.camera.z.toFixed(0)}) cm
            </div>
          </div>
        ) : (
        <Canvas
          camera={{ position: [size * 1.6, size * 1.1, size * 1.6], fov: 40 }}
          dpr={[1, 2]}
        >
          <ambientLight intensity={0.6} />
          <directionalLight position={[10, 10, 5]} intensity={0.8} />
          <color attach="background" args={["#0d0f14"]} />

          <Grid
            args={[size * 2.4, size * 2.4]}
            cellSize={size / 8}
            cellThickness={0.5}
            cellColor="#2a303c"
            sectionSize={size / 2}
            sectionThickness={1}
            sectionColor="#3a4150"
            fadeDistance={size * 3}
            fadeStrength={1}
            position={[0, -size * 0.45, 0]}
          />

          <AxisHelper size={size * 0.15} />

          {/* trajectory line */}
          {positions.length > 1 && (
            <AnimatedLine
              positions={positions}
              colors={colors.map((c) => [c.r, c.g, c.b] as [number, number, number])}
            />
          )}

          {/* dots */}
          {positions.map((p, i) => (
            <Waypoint
              key={frames[i].id}
              index={i}
              position={p}
              color={colors[i]}
              active={activeIndex === frames[i].frame_index}
              yaw={frames[i].camera.yaw}
              frameIndex={frames[i].frame_index}
              onClick={() => router.push(sessionId ? `/sessions/${sessionId}/frames/${frames[i].id}` : `/frames/${frames[i].id}`)}
            />
          ))}

          <OrbitControls
            enableDamping
            dampingFactor={0.1}
            minDistance={size * 0.6}
            maxDistance={size * 4}
            makeDefault
          />
        </Canvas>
        )}
      </div>
    </div>
  );
}

function AnimatedLine({
  positions,
  colors,
}: {
  positions: [number, number, number][];
  colors: [number, number, number][];
}) {
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const DURATION = 900;
    const DELAY = 900;
    const tick = (t: number) => {
      const elapsed = Math.max(0, t - start - DELAY);
      setProgress(Math.min(1, elapsed / DURATION));
      if (elapsed < DURATION) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  const visibleCount = Math.max(2, Math.floor(positions.length * progress));
  const pts = positions.slice(0, visibleCount);
  const cols = colors.slice(0, visibleCount);
  if (pts.length < 2) return null;

  return (
    <Line
      points={pts}
      vertexColors={cols}
      lineWidth={2}
      transparent
      opacity={0.9}
    />
  );
}

function Waypoint({
  index,
  position,
  color,
  active,
  yaw,
  frameIndex,
  onClick,
}: {
  index: number;
  position: [number, number, number];
  color: THREE.Color;
  active: boolean;
  yaw: number;
  frameIndex: number;
  onClick: () => void;
}) {
  const [hover, setHover] = useState(false);
  const [reveal, setReveal] = useState(false);
  const meshRef = useRef<THREE.Mesh>(null!);
  const haloRef = useRef<THREE.Mesh>(null!);

  useEffect(() => {
    const timer = setTimeout(() => setReveal(true), 200 + index * 40);
    return () => clearTimeout(timer);
  }, [index]);

  // subtle idle pulse on the active waypoint
  useFrame(({ clock }) => {
    if (!active || !haloRef.current) return;
    const s = 1 + Math.sin(clock.elapsedTime * 3) * 0.15;
    haloRef.current.scale.setScalar(s);
  });

  const radius = active ? 0.18 : hover ? 0.15 : 0.1;
  const yawRad = (yaw * Math.PI) / 180;

  return (
    <group
      position={position}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHover(true);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        setHover(false);
        document.body.style.cursor = "auto";
      }}
      scale={reveal ? 1 : 0}
    >
      {(hover || active) && (
        <mesh ref={haloRef}>
          <sphereGeometry args={[radius * 2.6, 16, 16]} />
          <meshBasicMaterial color={color} transparent opacity={0.18} />
        </mesh>
      )}
      <mesh ref={meshRef}>
        <sphereGeometry args={[radius, 24, 24]} />
        <meshBasicMaterial color={color} />
      </mesh>
      {/* yaw indicator — short line pointing where the camera faces */}
      <Line
        points={[
          [0, 0, 0],
          [Math.cos(yawRad) * radius * 3.2, 0, -Math.sin(yawRad) * radius * 3.2],
        ]}
        color={color}
        lineWidth={hover || active ? 2 : 1}
        transparent
        opacity={hover || active ? 0.9 : 0.45}
      />
      {(hover || active) && (
        <Billboard>
          <Html center distanceFactor={8} style={{ pointerEvents: "none" }}>
            <div
              className="rounded bg-[#07080b] border px-2 py-0.5 text-[11px] font-mono text-white"
              style={{ borderColor: `#${color.getHexString()}` }}
            >
              #{String(frameIndex).padStart(3, "0")}
            </div>
          </Html>
        </Billboard>
      )}
    </group>
  );
}

function AxisHelper({ size }: { size: number }) {
  return (
    <group>
      <Line
        points={[[0, 0, 0], [size, 0, 0]]}
        color="#f87171"
        lineWidth={2}
        transparent
        opacity={0.55}
      />
      <Line
        points={[[0, 0, 0], [0, size, 0]]}
        color="#4ade80"
        lineWidth={2}
        transparent
        opacity={0.55}
      />
      <Line
        points={[[0, 0, 0], [0, 0, size]]}
        color="#60a5fa"
        lineWidth={2}
        transparent
        opacity={0.55}
      />
    </group>
  );
}
