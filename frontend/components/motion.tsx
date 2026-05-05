"use client";

/* ─────────────────────────────────────────────────────────
 * MOTION PRIMITIVES
 *   Spring-first entrance/exit primitives. All timing comes
 *   from SPRING and TIMING — tune in one place, never inline.
 * ───────────────────────────────────────────────────────── */

import { motion, type Variants } from "framer-motion";
import type { ReactNode } from "react";

export const SPRING = {
  entrance:  { type: "spring", stiffness: 260, damping: 26, mass: 0.9 },
  hover:     { type: "spring", stiffness: 400, damping: 30 },
  tapSpring: { type: "spring", stiffness: 500, damping: 28 },
} as const;

export const TIMING = {
  // Base delays (seconds) applied from the TOP of each screen.
  heroIn:     0.00,
  kpiIn:      0.10,
  kpiStagger: 0.06,
  sectionIn:  0.22,
  gridIn:     0.30,
  gridStagger:0.035,
} as const;

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 8 },
  show:   { opacity: 1, y: 0, transition: SPRING.entrance as object },
};

/** A single element that fades + rises into view. */
export function FadeUp({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="show"
      variants={fadeUp}
      transition={{ ...(SPRING.entrance as object), delay }}
    >
      {children}
    </motion.div>
  );
}

/** Parent that reveals children in sequence. */
export function Stagger({
  children,
  delay = 0,
  gap = 0.05,
  className,
}: {
  children: ReactNode;
  delay?: number;
  gap?: number;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="show"
      variants={{
        hidden: {},
        show: { transition: { staggerChildren: gap, delayChildren: delay } },
      }}
    >
      {children}
    </motion.div>
  );
}

/** Child of Stagger — inherits the parent's timing sequence. */
export function StaggerItem({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div className={className} variants={fadeUp}>
      {children}
    </motion.div>
  );
}
