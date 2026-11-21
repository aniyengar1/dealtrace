"use client";

import { motion } from "framer-motion";
import type { ReactNode } from "react";

// Fade/slide-in the first time a section scrolls into view. Framer
// Motion's `whileInView` already no-ops under prefers-reduced-motion at
// the OS level isn't automatic, but the global CSS override in
// globals.css (animation/transition-duration: 0.01ms) still collapses
// this to an instant appearance, so reduced-motion users never wait on it.
export function Reveal({ children, className = "", delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 0.5, delay: delay / 1000, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
