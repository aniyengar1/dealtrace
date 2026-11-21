"use client";

import { useEffect, useRef, useState } from "react";
import { useInView, animate } from "framer-motion";
import { usePrefersReducedMotion } from "@/lib/useReducedMotion";

export function StatNumber({
  value,
  label,
  n,
  size = "md",
  prefix = "",
  suffix = "",
  decimals = 0,
}: {
  value: number;
  label: string;
  n?: number;
  size?: "md" | "lg";
  prefix?: string;
  suffix?: string;
  decimals?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.6 });
  const prefersReducedMotion = usePrefersReducedMotion();
  // Starts at the real final value, not 0 -- server HTML, no-JS
  // requests, link-preview scrapers, and screen readers before
  // hydration all see the true number. The count-up below is a
  // purely cosmetic re-animation that kicks in only after mount.
  const [display, setDisplay] = useState(value);

  useEffect(() => {
    if (!inView || prefersReducedMotion) return;
    // animate()'s onUpdate fires with the `from` value (0) on its very
    // first tick, so the reset-then-count-up is driven entirely from
    // that callback -- never a direct setState in the effect body.
    const controls = animate(0, value, {
      duration: 0.6,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: setDisplay,
    });
    return () => controls.stop();
  }, [inView, value, prefersReducedMotion]);

  const finalText = `${prefix}${value.toFixed(decimals)}${suffix}`;

  return (
    <div className="rounded-lg bg-bg/55 px-4 py-3 backdrop-blur-sm">
      <span
        ref={ref}
        aria-label={finalText}
        className={`font-serif tabular-nums text-accent ${size === "lg" ? "text-4xl sm:text-5xl" : "text-3xl"}`}
      >
        {prefix}
        {display.toFixed(decimals)}
        {suffix}
      </span>
      <p className="mt-1.5 text-sm text-ink-muted">
        {label}
        {n !== undefined && <span className="text-ink"> (n = {n})</span>}
      </p>
    </div>
  );
}
